import os
import json
import base64
import typing
import logging
import tempfile
import subprocess

import celery

from .. import config, common
from ..celery import app as celery_app

from . import cloudcli
from . import rke2

if typing.TYPE_CHECKING:
    from .nodepool import NodePool


class NodeException(common.CloudcliException):
    pass


class Node:

    def __init__(self, nodepool: 'NodePool', node_number: int):
        self.nodepool = nodepool
        self.node_number = node_number

    def get_celery_runner(self):
        return NodeCeleryRunner(self)

    def get_create_celery_signature(self):
        from cloudcli_server_kubernetes.tasks import create_node
        return create_node.si(
            self.nodepool.cluster.cnf.export(),
            self.nodepool.name,
            self.node_number
        )

    def get_update_celery_signature(self):
        from cloudcli_server_kubernetes.tasks import update_node
        return update_node.si(
            self.nodepool.cluster.cnf.export(),
            self.nodepool.name,
            self.node_number,
        )

    @property
    def server_name_prefix(self):
        return f'{self.nodepool.cluster.name}-{self.nodepool.name}-{self.node_number}'

    @property
    def creds(self):
        return self.nodepool.cluster.cnf.creds

    def create_server(self):
        command_id = cloudcli.find_server_command_in_queue(cloudcli.CREATE_SERVER_COMMAND_INFO, self.server_name_prefix, self.creds)
        if not command_id:
            node_config = {
                **config.DEFAULT_SERVER_CONFIG,
                **self.nodepool.node_pool_config
            }
            data = {
                "name": cloudcli.get_server_name(self.server_name_prefix),
                "password": "",
                "passwordValidate": "",
                "ssh-key": self.nodepool.cluster.cnf.ssh_key_public,
                "datacenter": self.nodepool.cluster.cnf.datacenter,
                "image": node_config['image'],
                "cpu": node_config['cpu'],
                "ram": node_config['ram'],
                "disk": node_config['disk'],
                "dailybackup": node_config['dailybackup'],
                "managed": node_config['managed'],
                "network": f"id=0,name=wan,ip=auto id=1,name={self.nodepool.cluster.cnf.private_network_name},ip=auto",
                "quantity": 1,
                "billingcycle": node_config['billingcycle'],
                "monthlypackage": node_config['monthlypackage'],
                "poweronaftercreate": "yes",
            }
            logging.debug(f'Creating server\n{json.dumps(data, indent=2)}')
            status, res = cloudcli.cloudcli_server_request("/service/server", self.creds, method="POST", json=data)
            if status != 200 or len(res) != 1:
                raise NodeException(f'Create server failed: {status} {res}')
            command_id = res[0]
        cloudcli.wait_command(self.creds, command_id)
        server_info = self.get_server_info()
        if not server_info:
            raise NodeException('Server not found after creation')
        return server_info

    def create(self):
        server_info = self.get_server_info()
        if not server_info:
            server_info = self.create_server()
        is_server = self.nodepool.cluster.cnf.node_pools[self.nodepool.name].is_server
        if self.nodepool.name == 'controlplane' and self.node_number == 1:
            cluster_server, cluster_token = None, None
        else:
            cluster_server, cluster_token = self.nodepool.cluster.get_cluster_server_token()
        rke2_init_script = rke2.get_rke2_init_script(
            self.server_name_prefix,
            is_server,
            cluster_server,
            cluster_token,
        )
        rke2_systemd_unit = rke2.get_rke2_systemd_unit(is_server)
        self.ssh_run_script(f'''
            if systemctl is-active {rke2_systemd_unit}; then
                echo RKE2 already installed
            else
                {rke2_init_script}
            fi
        ''', server_info)
        return {
            'nodepool_name': self.nodepool.name,
            'node_number': self.node_number,
            'message': 'Server Created Successfully',
        }

    def get_server_info(self):
        return cloudcli.get_server_info(self.creds, self.server_name_prefix)

    def get_public_private_ips(self, server_info=None):
        if not server_info:
            server_info = self.get_server_info()
        return cloudcli.get_server_public_private_ips(server_info)

    def ssh(self, command, server_info=None):
        public_ip, _ = self.get_public_private_ips(server_info)
        with tempfile.TemporaryDirectory() as tmpdir:
            filename = os.path.join(tmpdir, 'id_rsa')
            with open(filename, 'w') as f:
                f.write(self.nodepool.cluster.cnf.ssh_key_private)
            os.chmod(filename, 0o600)
            return subprocess.check_output([
                'ssh', '-i', filename, '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null', f'root@{public_ip}', command
            ], text=True)

    def ssh_run_script(self, script, server_info=None):
        script_b64 = base64.b64encode(script.encode()).decode()
        return self.ssh(f'echo {script_b64} | base64 -d | bash', server_info)

    def kubectl(self, command, server_info=None):
        return self.ssh(f'KUBECONFIG=/etc/rancher/rke2/rke2.yaml /var/lib/rancher/rke2/bin/kubectl {command}', server_info)

    def update(self):
        server_info = self.get_server_info()
        if not server_info:
            raise NodeException('Server does not exist')
        is_server = self.nodepool.cluster.cnf.node_pools[self.nodepool.name].is_server
        if self.nodepool.name == 'controlplane' and self.node_number == 1:
            cluster_server, cluster_token = None, None
        else:
            cluster_server, cluster_token = self.nodepool.cluster.get_cluster_server_token()
        rke2_update_script = rke2.get_rke2_update_script(
            self.server_name_prefix,
            is_server,
            cluster_server,
            cluster_token,
        )
        self.ssh(rke2_update_script, server_info)
        return {
            'nodepool_name': self.nodepool.name,
            'node_number': self.node_number,
            'message': 'Server Updated Successfully',
        }


class NodeCeleryRunner:

    def __init__(self, node):
        self.node = node

    def create(self, task: celery.Task):
        return common.CeleryRunnerResult(
            'create_node', self.node.create, self.node.creds,
            meta={'nodepool_name': self.node.nodepool.name, 'node_number': self.node.node_number}
        ).export()

    def update(self, task: celery.Task):
        return common.CeleryRunnerResult(
            'update_node', self.node.update, self.node.creds,
            meta={'nodepool_name': self.node.nodepool.name, 'node_number': self.node.node_number}
        ).export()
