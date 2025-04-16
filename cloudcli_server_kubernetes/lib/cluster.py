from functools import partial

import celery
from celery.result import GroupResult
from ruamel.yaml import YAML, StringIO

from .nodepool import NodePool
from .cnf import Cnf
from .. import common


class ClusterException(common.CloudcliException):
    pass


class Cluster:

    def __init__(self, cnf: Cnf):
        self.cnf = cnf
        self.node_pools = {
            nodepool_name: NodePool(self, nodepool_name)
            for nodepool_name in self.cnf.node_pools.keys()
        }

    @classmethod
    def init_from_cnf_creds(cls, cnf, creds=None):
        return cls(Cnf(cnf, creds))

    @property
    def name(self):
        return self.cnf.name

    def get_cluster_server_token(self, controlplane_server_info=None):
        controlplane_node = self.node_pools['controlplane'].get_node(1)
        cluster_server = self.cnf.cluster_server
        cluster_token = self.cnf.cluster_token
        if not cluster_server or not cluster_token:
            if not controlplane_server_info:
                controlplane_server_info = controlplane_node.get_server_info()
            if not controlplane_server_info:
                raise ClusterException('Controlplane server not found')
            public_ip, private_ip = controlplane_node.get_public_private_ips(controlplane_server_info)
            if not cluster_server:
                cluster_server = f"https://{public_ip}:9345"
            if not cluster_token:
                cluster_token = controlplane_node.ssh('cat /var/lib/rancher/rke2/server/node-token', controlplane_server_info).strip()
        assert cluster_server and cluster_token, 'Cluster server and token are missing'
        return cluster_server, cluster_token

    def get_status(self):
        common.logging.debug('Cluster.get_status')
        controlplane_node = self.node_pools['controlplane'].get_node(1)
        controlplane_server_info = controlplane_node.get_server_info()
        controlplane_public_ip, controlplane_private_ip = controlplane_node.get_public_private_ips(controlplane_server_info)
        cluster_server, _ = self.get_cluster_server_token(controlplane_server_info)
        status = {
            'cluster_server': cluster_server,
            'controlplane_public_ip': controlplane_public_ip,
            'controlplane_private_ip': controlplane_private_ip,
            'node_pools': {}
        }
        for node_pool_name, node_pool in self.node_pools.items():
            status['node_pools'][node_pool_name] = {
                node_number: node_pool.get_node(node_number).get_server_info()
                for node_number in node_pool.node_numbers()
            }
        status['kubectl_version'] = str(controlplane_node.kubectl('version', controlplane_server_info)).strip().split('\n')
        status['kubectl_top_node'] = str(controlplane_node.kubectl('top node', controlplane_server_info)).strip().split('\n')
        return status

    def get_kubeconfig(self):
        controlplane_node = self.node_pools['controlplane'].get_node(1)
        controlplane_server_info = controlplane_node.get_server_info()
        kubeconfig = self.node_pools['controlplane'].get_node(1).ssh('cat /etc/rancher/rke2/rke2.yaml', controlplane_server_info)
        public_ip, _ = controlplane_node.get_public_private_ips(controlplane_server_info)
        kubeconfig = YAML(typ='safe').load(kubeconfig)
        kubeconfig['clusters'][0]['cluster']['server'] = f'https://{public_ip}:6443'
        stream = StringIO()
        YAML(typ='safe').dump(kubeconfig, stream)
        return stream.getvalue()


class ClusterCeleryRunner:

    def __init__(self, cluster: Cluster):
        self.cluster = cluster

    @classmethod
    def init_from_cnf_creds(cls, cnf, creds=None):
        return cls(Cluster.init_from_cnf_creds(cnf, creds))

    def get_nodepool_celery_runner(self, nodepool_name):
        return self.cluster.node_pools[nodepool_name].get_celery_runner()

    def get_node_celery_runner(self, nodepool_name, node_number):
        return self.cluster.node_pools[nodepool_name].get_node(node_number).get_celery_runner()

    def create(self, task: celery.Task):
        from cloudcli_server_kubernetes.tasks import create_nodepool
        return ClusterCeleryRunnerResult('create', partial(self.create_update, task, create_nodepool), self.cluster.cnf.creds).export()

    def update(self, task: celery.Task):
        from cloudcli_server_kubernetes.tasks import update_nodepool
        return ClusterCeleryRunnerResult('update', partial(self.create_update, task, update_nodepool), self.cluster.cnf.creds).export()

    def get_cluster_status(self, task: celery.Task):
        return ClusterCeleryRunnerResult('get_cluster_status', self.cluster.get_status, self.cluster.cnf.creds).export()

    def get_kubeconfig(self, task: celery.Task):
        return ClusterCeleryRunnerResult('get_kubeconfig', self.cluster.get_kubeconfig, self.cluster.cnf.creds).export()

    def create_update(self, task: celery.Task, create_update_task):
        cnf = self.cluster.cnf.export()
        group_result: GroupResult = celery.chain(
            create_update_task.si(cnf, 'controlplane'),
            celery.group(
                create_update_task.si(cnf, nodepool_name)
                for nodepool_name in self.cluster.node_pools.keys()
                if nodepool_name != 'controlplane'
            )
        ).delay()
        task_ids = [group_result.id]
        result = group_result
        while result.parent:
            task_ids.append(result.parent.id)
            result = result.parent
        return {
            'task_ids': task_ids,
        }


class ClusterCeleryRunnerResult(common.CeleryRunnerResult):
    object_name = 'cluster'

    def get_task_status_meta(self):
        if self.task_name in ['create', 'update']:
            return self.result
        else:
            return super().get_task_status_meta()

    def get_task_status(self):
        if self.task_name in ['create', 'update']:
            return self.get_multi_tasks_status(
                f'{self.task_name}_cluster',
                self.result['task_ids'] if not self.error else []
            )
        else:
            return super().get_task_status()
