import os
import json
import tempfile

from celery.contrib.testing import worker as celery_worker

from cloudcli_server_kubernetes import tasks, common


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
    },
    "node-pools": {
        "worker1": {
            "nodes": 3,
            "node-config": {
                "cpu": "4B",
                "memory": 2048
            }
        }
    }
}


def test_cluster_celery_runner_create(monkeypatch):
    state = {
        'commands': {},
        'created_node_pools': {},
        'mock_node_ssh_calls': [],
    }

    def mock_cloudcli_server_request(path, *args, **kwargs):
        if path == '/service/server/info' and kwargs.get('json', {}).get('name') in [f'test-cluster-{n}-.*' for n in ['controlplane-1', 'worker1-1', 'worker1-2', 'worker1-3']]:
            for node_pool_name, nodes in state['created_node_pools'].items():
                for node_num, node in nodes.items():
                    if kwargs['json']['name'] == f'test-cluster-{node_pool_name}-{node_num}-.*':
                        return 200, [{
                            **node['command']['kwargs']['json'],
                            'networks': [
                                {
                                    'network': 'wan-a',
                                    'ips': ['1.2.3.4']
                                },
                                {
                                    'network': 'lan-b',
                                    'ips': ['10.0.0.2']
                                }
                            ]
                        }]
            return 200, []
        elif path == '/svc/queue':
            return 200, []
        elif path == '/service/server' and kwargs.get('method') == 'POST':
            command_id = str(len(state['commands']))
            state['commands'][command_id] = {
                'path': path,
                'args': args,
                'kwargs': kwargs,
            }
            return 200, [command_id]
        elif path.startswith('/service/queue?id='):
            command_id = path.split('=')[1]
            command = state['commands'][command_id]
            assert command['path'] == '/service/server'
            server = command['kwargs']['json']
            assert server['name'].startswith('test-cluster-')
            _, _, nodepool_name, node_num, *_ = server['name'].split('-')
            if nodepool_name == 'worker1':
                assert node_num in ['1', '2', '3']
            else:
                assert nodepool_name == 'controlplane' and node_num == '1'
            state['created_node_pools'].setdefault(nodepool_name, {})[node_num] = {
                'command': command
            }
            return 200, [{'status': 'complete'}]
        else:
            raise Exception(f'unexpected mock_cloudcli_server_request {path} {args} {kwargs}')

    def mock_node_ssh(self, command, server_info=None):
        state['mock_node_ssh_calls'].append([command, server_info])
        if command == 'cat /var/lib/rancher/rke2/server/node-token':
            return 'test-token'

    monkeypatch.setattr("cloudcli_server_kubernetes.lib.cloudcli.cloudcli_server_request", mock_cloudcli_server_request)
    monkeypatch.setattr("cloudcli_server_kubernetes.lib.node.Node.ssh", mock_node_ssh)
    with tempfile.TemporaryDirectory() as tmpdir:
        tasks.app.conf.update(
            result_backend='db+sqlite:///' + os.path.join(tmpdir, 'celery_results.db'),
            broker_url='memory://',
        )
        with celery_worker.start_worker(tasks.app, perform_ping_check=False):
            common.setup_logging(level='DEBUG', force=True)
            creds = ('aaa', 'bbb')
            task_id = tasks.create_cluster.delay(MINIMAL_CNF, creds=creds).id
            res = common.wait_task_status(task_id, creds)
            assert res.keys() == {'task_id', 'task_name', 'state', 'result', 'error', 'meta'}
            assert res['task_name'] == 'create_cluster'
            assert res['state'] == 'SUCCESS'
            assert res['result'] == [
                [
                  {
                    "nodepool_name": "worker1",
                    "node_number": 1,
                    "message": "Server Created Successfully"
                  },
                  {
                    "nodepool_name": "worker1",
                    "node_number": 2,
                    "message": "Server Created Successfully"
                  },
                  {
                    "nodepool_name": "worker1",
                    "node_number": 3,
                    "message": "Server Created Successfully"
                  }
                ],
                [
                  {
                    "nodepool_name": "controlplane",
                    "node_number": 1,
                    "message": "Server Created Successfully"
                  }
                ]
              ]
            assert res['error'] is None
            assert res['meta'].keys() == {'task_ids', 'subtasks'}
            assert len(res['meta']['task_ids']) == 2
            assert len(res['meta']['subtasks']) == 2
    assert len(state['commands']) == 4
    assert state['created_node_pools'].keys() == {'worker1', 'controlplane'}
