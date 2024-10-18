import json
import logging
import base64

from . import common


RKE2_VERSION = 'v1.31.1+rke2r1'


def get_server_init_script(cnf, nodepool_name=None, node_number=None, is_server=False, cluster_server=None, cluster_token=None):
    """
    internal function to generate the server init script
    """
    cluster_name = cnf['cluster']['name']
    rke2_config = {
        'node-name': common.get_server_name(cluster_name, nodepool_name, node_number, with_suffix=False),
        'node-ip': "${PRIVATE_IP}",
        'node-external-ip': "${PUBLIC_IP}",
    }
    if is_server:
        assert not cluster_server and not cluster_token
        rke2_config.update({
            'bind-address': "${PRIVATE_IP}",
            'advertise-address': "${PRIVATE_IP}",
            'tls-san': [
                "${PRIVATE_IP}"
            ],
        })
    else:
        assert cluster_server and cluster_token
        rke2_config['server'] = cluster_server
        rke2_config['token'] = cluster_token
    rke2_config_b64 = base64.b64encode(json.dumps(rke2_config).encode()).decode()
    rke2_type = 'server' if is_server else 'agent'
    return ' && '.join([
        "ufw default deny incoming",
        "ufw default allow outgoing",
        "ufw allow 22",
        "ufw allow in on eth1",
        "ufw --force enable",
        "export PUBLIC_IP=$(echo $(ip -4 addr show dev eth0 | grep inet) | cut -d' ' -f2 | cut -d'/' -f1)",
        "export PRIVATE_IP=$(echo $(ip -4 addr show dev eth1 | grep inet) | cut -d' ' -f2 | cut -d'/' -f1)",
        'mkdir -p /etc/rancher/rke2',
        f'echo {rke2_config_b64} | base64 -d | envsubst > /etc/rancher/rke2/config.yaml',
        f'curl -sfL https://get.rke2.io | INSTALL_RKE2_VERSION={RKE2_VERSION} INSTALL_RKE2_TYPE={rke2_type} sh -',
        f'systemctl enable rke2-{rke2_type}',
        f'systemctl start rke2-{rke2_type}',
        "echo PATH='$PATH:/var/lib/rancher/rke2/bin' >> ~/.bashrc",
        'echo export KUBECONFIG=/etc/rancher/rke2/rke2.yaml >> ~/.bashrc',
    ])


def create_server(cnf, nodepool_name=None, node_number=None, is_server=False, cluster_server=None, cluster_token=None, creds=None):
    """
    Internal function to initiate server creation
    returns command_id of the create server command
    """
    cluster_name = cnf['cluster']['name']
    if is_server:
        assert not nodepool_name and not node_number
        node_number = 1
        nodepool_name = 'controlplane'
    else:
        assert node_number and nodepool_name and nodepool_name != 'controlplane'
        node_number = int(node_number)
    server_info = common.get_server_info(cluster_name, nodepool_name, node_number, creds=creds)
    if server_info:
        raise CloudcliApiException('Server already exists')
    command_id = common.find_server_command_in_queue('Create Server', cluster_name, nodepool_name, node_number, creds=creds)
    if not command_id:
        node_config = cnf['node-pools'][nodepool_name]['nodes'][node_number]
        data = {
            "name": common.get_server_name(cluster_name, nodepool_name, node_number),
            "password": "",
            "passwordValidate": "",
            "ssh-key": cnf['cluster']['ssh-key']['public'],
            "datacenter": cnf['cluster']['datacenter'],
            "image": node_config['image'],
            "cpu": node_config['cpu'],
            "ram": node_config['ram'],
            "disk": node_config['disk'],
            "dailybackup": node_config['dailybackup'],
            "managed": node_config['managed'],
            "network": f"id=0,name=wan,ip=auto id=1,name={cnf['cluster']['private-network']['name']},ip=auto",
            "quantity": 1,
            "billingcycle": node_config['billingcycle'],
            "monthlypackage": node_config['monthlypackage'],
            "poweronaftercreate": "yes",
            "script-file": get_server_init_script(cnf, nodepool_name, node_number, is_server, cluster_server, cluster_token)
        }
        logging.debug(f'Creating server\n{json.dumps(data, indent=2)}')
        status, res = common.cloudcli_server_request("/service/server", method="POST", json=data, creds=creds)
        if status != 200 or len(res) != 1:
            raise CloudcliApiException(f'Create server failed: {status} {res}')
        command_id = res[0]
    return command_id


def create_cluster(cnf, creds=None):
    return create_server(cnf, is_server=True, creds=creds)


def add_worker(cnf, nodepool_name, node_number, creds=None):
    cluster_server, cluster_token = common.get_cluster_server_token(cnf, creds=creds)
    return create_server(cnf, nodepool_name, node_number, cluster_server=cluster_server, cluster_token=cluster_token, creds=creds)


def cluster_status(cnf, full=False, creds=None):
    controlplane_server_info = common.get_controlplane_server_info(cnf, creds=creds)
    controlplane_public_ip, controlplane_private_ip = common.get_server_ips(controlplane_server_info)
    cluster_server, _ = common.get_cluster_server_token(cnf, creds=creds, controlplane_server_info=controlplane_server_info)
    status = {
        'cluster_server': cluster_server,
        'controlplane_public_ip': controlplane_public_ip,
        'controlplane_private_ip': controlplane_private_ip,
        'controlplane_server': controlplane_server_info,
        'node_pools': {}
    }
    for node_pool_name, node_pool_config in cnf['node-pools'].items():
        if node_pool_name != 'controlplane':
            if full:
                status['node_pools'][node_pool_name] = {
                    k: common.get_server_info(cnf['cluster']['name'], node_pool_name, k, creds=creds)
                    for k in node_pool_config['nodes']
                }
            else:
                status['node_pools'][node_pool_name] = {
                    k: {
                        'name': common.get_server_name(cnf['cluster']['name'], node_pool_name, k, with_suffix=False)
                    } for k in node_pool_config['nodes']
                }
    if full:
        status['kubectl_version'] = str(common.kubectl(cnf, controlplane_public_ip, 'version')).strip().split('\n')
        status['kubectl_top_node'] = str(common.kubectl(cnf, controlplane_public_ip, 'top node')).strip().split('\n')
    return status


class CloudcliApiException(Exception):
    pass
