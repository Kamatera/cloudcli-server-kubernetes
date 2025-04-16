import os
import json
from typing import Optional
from functools import cached_property

from ruamel.yaml import YAML

from .. import common, config


class CnfConfigError(common.CloudcliException):
    pass


def parse_file(file):
    if file:
        file = os.path.expanduser(file)
        if os.path.exists(file):
            with open(file) as f:
                return f.read()
        else:
            return file
    else:
        return None


class CnfNodePool:

    def __init__(self, cnf, node_pool_name, node_pool_config):
        self.cnf = cnf
        self.node_pool_name = node_pool_name
        self.node_pool_config = node_pool_config

    def validate(self):
        msg = f'node-pools.{self.node_pool_name}'
        try:
            assert self.name, f'{msg}.name is required'
            assert len(self.nodes) > 0, f'{msg}.nodes is required'
            if not self.cnf.allow_high_availability and self.name == 'controlplane':
                assert len(self.nodes) == 1, f'{msg}.nodes must be 1 when high availability is disabled'
        except AssertionError as e:
            raise CnfConfigError(str(e))

    @cached_property
    def name(self) -> str:
        return self.node_pool_name

    @cached_property
    def nodes(self) -> list[int]:
        nodes = self.node_pool_config['nodes']
        if isinstance(nodes, list):
            return [int(node_num) for node_num in nodes]
        else:
            nodes = int(nodes)
            return [i for i in range(1, nodes + 1)]

    @cached_property
    def node_config(self) -> dict:
        return {
            **self.cnf.default_node_config,
            **(self.node_pool_config.get('node-config') or {}),
        }

    @cached_property
    def is_server(self) -> bool:
        return self.node_pool_name == 'controlplane'

    @cached_property
    def rke2_config(self) -> dict:
        return {
            **(self.cnf.default_rke2_server_config if self.is_server else self.cnf.default_rke2_agent_config),
            **(self.node_pool_config.get('rke2-config') or {}),
        }


class Cnf:

    def __init__(self, cnf, creds=None):
        if not isinstance(cnf, dict):
            if os.path.exists(cnf):
                with open(cnf) as f:
                    if cnf.endswith('.json'):
                        try:
                            cnf = json.load(f)
                        except:
                            raise CnfConfigError('Invalid JSON file')
                    elif cnf.endswith('.yaml'):
                        cnf = YAML(typ='safe').load(f)
                    else:
                        raise CnfConfigError('Unsupported file format')
            else:
                cnf = YAML(typ='safe').load(cnf)
        if not isinstance(cnf, dict):
            raise CnfConfigError('Invalid config format')
        self.cnf = cnf
        if not self.cnf.get('__creds'):
            if creds == 'env':
                creds = config.KAMATERA_API_CLIENT_ID, config.KAMATERA_API_SECRET
            self.cnf['__creds'] = creds
        self.validate()

    def validate(self):
        try:
            assert self.name, 'cluster.name is required'
            assert self.datacenter, 'cluster.datacenter is required'
            assert self.ssh_key_private, 'cluster.ssh-key.private is required'
            assert self.ssh_key_public, 'cluster.ssh-key.public is required'
            assert self.private_network_name, 'cluster.private-network.name is required'
            for node_pool in self.node_pools.values():
                node_pool.validate()
            assert self.auth_client_id and self.auth_secret, 'Auth credentials are missing'
        except AssertionError as e:
            raise CnfConfigError(str(e))

    def export(self):
        return json.dumps(self.cnf)

    @cached_property
    def auth_client_id(self) -> str:
        return self.cnf['__creds'][0] if self.cnf.get('__creds') else None

    @cached_property
    def auth_secret(self) -> str:
        return self.cnf['__creds'][1] if self.cnf.get('__creds') else None

    @cached_property
    def creds(self) -> tuple:
        return self.auth_client_id, self.auth_secret

    @cached_property
    def cluster(self):
        return self.cnf.get('cluster', {})

    @cached_property
    def name(self) -> str:
        return self.cluster.get('name')

    @cached_property
    def datacenter(self) -> str:
        return self.cluster.get('datacenter')

    @cached_property
    def ssh_key_private(self) -> str:
        return parse_file(self.cluster.get('ssh-key', {}).get('private'))

    @cached_property
    def ssh_key_public(self) -> str:
        return parse_file(self.cluster.get('ssh-key', {}).get('public'))

    @cached_property
    def private_network_name(self) -> str:
        return self.cluster.get('private-network', {}).get('name')

    @cached_property
    def cluster_server(self) -> Optional[str]:
        return self.cluster.get('server')

    @cached_property
    def cluster_token(self) -> Optional[str]:
        return self.cluster.get('token')

    @cached_property
    def controlplane_server_name(self) -> Optional[str]:
        return self.cluster.get('controlplane-server-name')

    @cached_property
    def allow_high_availability(self) -> bool:
        return bool(self.cluster.get('allow-high-availability'))

    @cached_property
    def default_node_config(self) -> dict:
        return self.cnf.get('default-node-config', {})

    @cached_property
    def default_rke2_server_config(self) -> dict:
        return self.cnf.get('default-rke2-server-config', {})

    @cached_property
    def default_rke2_agent_config(self) -> dict:
        return self.cnf.get('default-rke2-agent-config', {})

    @cached_property
    def node_pools(self) -> dict[str, CnfNodePool]:
        node_pools = self.cnf.get('node-pools', {})
        if 'controlplane' not in node_pools:
            node_pools['controlplane'] = {'nodes': 1}
        return {
            node_pool_name: CnfNodePool(self, node_pool_name, node_pool_config)
            for node_pool_name, node_pool_config in node_pools.items()
        }
