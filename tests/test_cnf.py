import json
import tempfile
from io import StringIO

import pytest
from ruamel.yaml import YAML

from cloudcli_server_kubernetes.lib.cnf import Cnf, CnfNodePool, CnfConfigError


def yaml_dump(data):
    stream = StringIO()
    YAML(typ='safe').dump(data, stream)
    return stream.getvalue()


MINIMAL_CNF = {
    "cluster": {
        "name": "test-cluster",
        "datacenter": "test-datacenter",
        "ssh-key": {
            "private": "test-private-key",
            "public": "test-public-key"
        },
        "private-network": {
            "name": "test-private-network"
        }
    }
}


@pytest.mark.parametrize("input_cnf, expected_cnf, file_name", [
    (yaml_dump(MINIMAL_CNF), MINIMAL_CNF, ''),
    (json.dumps(MINIMAL_CNF), MINIMAL_CNF, ''),
    ('', CnfConfigError('Invalid config format'), ''),
    (yaml_dump(MINIMAL_CNF), MINIMAL_CNF, 'test.yaml'),
    ('', CnfConfigError('Invalid config format'), 'test.yaml'),
    (json.dumps(MINIMAL_CNF), MINIMAL_CNF, 'test.json'),
    ('', CnfConfigError('Invalid JSON file'), 'test.json'),
])
def test_minimal(input_cnf, expected_cnf, file_name):
    with tempfile.TemporaryDirectory() as tmpdir:
        if file_name:
            file_path = f"{tmpdir}/{file_name}"
            with open(file_path, 'w') as f:
                f.write(input_cnf)
            input_cnf = file_path
        try:
            cnf = Cnf(input_cnf, ('key', 'secret'))
        except CnfConfigError as e:
            if isinstance(expected_cnf, CnfConfigError):
                assert str(e) == str(expected_cnf)
                return
            else:
                raise
        assert cnf.name == expected_cnf['cluster']['name']
        assert cnf.datacenter == expected_cnf['cluster']['datacenter']
        assert cnf.ssh_key_public == expected_cnf['cluster']['ssh-key']['public']
        assert cnf.ssh_key_private == expected_cnf['cluster']['ssh-key']['private']
        assert cnf.private_network_name == expected_cnf['cluster']['private-network']['name']
        assert cnf.node_pools.keys() == {'controlplane'}
        np = cnf.node_pools['controlplane']
        assert isinstance(np, CnfNodePool)
        assert np.name == 'controlplane'
        assert np.nodes == [1]
        assert np.node_config == {}
        assert np.is_server
        assert np.rke2_config == {}
