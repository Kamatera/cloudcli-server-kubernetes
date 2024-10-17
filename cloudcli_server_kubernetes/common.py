import os
import json
import secrets
import tempfile
import subprocess

import requests
from ruamel.yaml import YAML

from . import config


DEFAULT_NODE_CONFIG = {
    "image": "ubuntu_server_24.04_64-bit",
    "cpu": "2B",
    "ram": "4096",
    "disk": "size=100",
    "dailybackup": "no",
    "managed": "no",
    "billingcycle": "hourly",
    "monthlypackage": "",
}


def parse_file(file):
    file = os.path.expanduser(file)
    if os.path.exists(file):
        with open(file) as f:
            return f.read()
    else:
        return file


def parse_config(cnf):
    if os.path.exists(cnf):
        with open(cnf) as f:
            if cnf.endswith('.json'):
                cnf = json.load(f)
            elif cnf.endswith('.yaml'):
                cnf = YAML(typ='safe').load(f)
            else:
                raise ValueError(f'Unsupported file format: {cnf}')
    else:
        if not isinstance(cnf, dict):
            cnf = json.loads(cnf)
    cnf['cluster']['ssh-key']['private'] = parse_file(cnf['cluster']['ssh-key']['private'])
    cnf['cluster']['ssh-key']['public'] = parse_file(cnf['cluster']['ssh-key']['public'])
    default_node_config = cnf['cluster'].get('default-node-config') or {}
    node_pools = cnf.get('node-pools') or {}
    if 'controlplane' not in node_pools:
        node_pools['controlplane'] = {'nodes': 1}
    for node_pool_name, node_pool_config in node_pools.items():
        nodes = node_pool_config.get('nodes') or []
        if isinstance(nodes, int):
            nodes = {int(i): {} for i in range(1, nodes + 1)}
        elif isinstance(nodes, list):
            nodes = {int(i): {} for i in nodes}
        assert isinstance(nodes, dict)
        for k in nodes:
            nodes[k] = {
                **DEFAULT_NODE_CONFIG,
                **default_node_config,
                **(node_pool_config.get('default-node-config') or {}),
            }
        node_pools[node_pool_name]['nodes'] = nodes
    cnf['node-pools'] = node_pools
    assert len(cnf['node-pools']['controlplane']['nodes']) == 1
    return cnf


def cloudcli_server_request(path, **kwargs):
    url = "%s%s" % (config.KAMATERA_API_SERVER, path)
    method = kwargs.pop("method", "GET")
    res = requests.request(method=method, url=url, headers={
        "AuthClientId": config.KAMATERA_API_CLIENT_ID,
        "AuthSecret": config.KAMATERA_API_SECRET,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }, **kwargs)
    try:
        data = res.json()
    except:
        data = None
    return res.status_code, data


def get_server_name(cluster_name, nodepool_name, node_number=None, with_suffix=True):
    if not node_number:
        node_number = ''
        assert not with_suffix
    else:
        node_number = str(int(node_number))
    server_name = f"{cluster_name}-{nodepool_name}-{node_number}"
    if with_suffix:
        server_name += f"-{secrets.token_urlsafe(5)}"
    return server_name


def find_server_command_in_queue(command_info, cluster_name, nodepool_name, node_number):
    node_number = int(node_number)
    status, res = cloudcli_server_request("/svc/queue")
    assert status == 200
    for row in res:
        if (
            str(row.get('commandInfo')) == command_info
            and str(row.get('serviceName')).startswith(get_server_name(cluster_name, nodepool_name, node_number, with_suffix=False))
        ):
            return row['id']
    return None


def get_server_info(cluster_name, nodepool_name, node_number):
    status, res = cloudcli_server_request("/service/server/info", method="POST", json={
        "name": f'{get_server_name(cluster_name, nodepool_name, node_number, with_suffix=False)}-.*'
    })
    if status != 200:
        assert 'No servers found' in res['message'], f'Unexpected error {status}: {res}'
        res = []
    if len(res) == 0:
        return None
    elif len(res) > 1:
        raise Exception(f"Multiple matching servers found: {','.join([s['name'] for s in res])}")
    else:
        return res[0]


def get_server_ips(server_info):
    public_ip, private_ip = None, None
    for network in server_info['networks']:
        if not public_ip and network['network'].startswith('wan-'):
            public_ip = network['ips'][0]
        elif not private_ip:
            private_ip = network['ips'][0]
    assert public_ip and private_ip, 'Both public and private IPs are required'
    return public_ip, private_ip


def ssh(cnf, ip, command):
    with tempfile.TemporaryDirectory() as tmpdir:
        filename = os.path.join(tmpdir, 'id_rsa')
        with open(filename, 'w') as f:
            f.write(cnf['cluster']['ssh-key']['private'])
        os.chmod(filename, 0o600)
        return subprocess.check_output([
            'ssh', '-i', filename, '-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null', f'root@{ip}', command
        ], text=True)


def get_cluster_server_token(cnf):
    cluster_server = cnf['cluster'].get('server')
    cluster_token = cnf['cluster'].get('token')
    if not cluster_server or not cluster_token:
        server_info = get_server_info(cnf['cluster']['name'], 'controlplane', 1)
        public_ip, private_ip = get_server_ips(server_info)
    if not cluster_server:
        cluster_server = f"https://{private_ip}:9345"
    if not cluster_token:
        cluster_token = ssh(cnf, public_ip, 'cat /var/lib/rancher/rke2/server/node-token').strip()
    return cluster_server, cluster_token
