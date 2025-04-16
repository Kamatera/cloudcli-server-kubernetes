import json
import base64

import click

from .lib.cnf import Cnf
from .lib.cluster import Cluster
from . import tasks, common


def cli_wait_task_status(task_id, wait):
    if wait:
        print(f'Waiting for task {task_id}')
        res = common.wait_task_status(task_id, 'env')
    else:
        res = common.get_task_status(task_id, 'env')
    res.pop('meta', None)
    res.pop('result', None)
    print(json.dumps(res, indent=2))


def parse_base64(data):
    if data.startswith('BASE64:'):
        data = base64.b64decode(data[7:]).decode('utf-8')
    return data


@click.group()
def main():
    pass


@main.command()
@click.argument('task_id')
@click.option('--result', is_flag=True)
@click.option('--meta', is_flag=True)
@click.option('--raw', is_flag=True)
@click.option('--wait', is_flag=True)
def task_status(task_id, result, meta, raw, wait):
    if raw:
        assert not result and not meta and not wait
        from .celery import app
        r = app.AsyncResult(task_id)
        res = {
            'task_id': r.id,
            'state': r.state,
            'result': r.result,
            'traceback': r.traceback
        }
    else:
        if wait:
            res = common.wait_task_status(task_id, 'env')
        else:
            res = common.get_task_status(task_id, 'env')
        if result:
            assert not meta
            res = res.get('result')
        elif meta:
            res = res.get('meta')
        else:
            res.pop('meta', None)
            res.pop('result', None)
    try:
        print(json.dumps(res, indent=2))
    except TypeError:
        print(res)
        print("Failed to parse")
        exit(1)


@main.group()
def cluster():
    pass


@cluster.command()
@click.argument('config')
def server_token(config):
    cluster_server, cluster_token = Cluster(Cnf(config, creds='env')).get_cluster_server_token()
    print(f'Cluster server: {cluster_server}')
    print(f'Cluster token: {cluster_token}')


@cluster.command()
@click.argument('config')
def status(config):
    print(json.dumps(Cluster(Cnf(config, creds='env')).get_status(), indent=2))


@cluster.command()
@click.argument('config')
def kubeconfig(config):
    print(Cluster(Cnf(config, creds='env')).get_kubeconfig())


@cluster.command()
@click.argument('config')
@click.option('--wait', is_flag=True)
def create(config, wait):
    config = parse_base64(config)
    cli_wait_task_status(tasks.create_cluster.delay(config, 'env').id, wait)


@cluster.command()
@click.argument('config')
@click.option('--wait', is_flag=True)
def update(config, wait):
    config = parse_base64(config)
    cli_wait_task_status(tasks.update_cluster.delay(config, 'env').id, wait)


@main.group()
def nodepool():
    pass


@nodepool.command()
@click.argument('config')
@click.argument('nodepool')
def node_numbers(config, nodepool):
    print(Cluster(Cnf(config, creds='env')).node_pools[nodepool].node_numbers())


@main.group()
def node():
    pass


@node.command()
@click.argument('config')
@click.argument('nodepool')
@click.argument('node_number')
def create(config, nodepool, node_number):
    print(json.dumps(Cluster(Cnf(config, creds='env')).node_pools[nodepool].get_node(int(node_number)).create(), indent=2))


@node.command()
@click.argument('config')
@click.argument('nodepool')
@click.argument('node_number')
def update(config, nodepool, node_number):
    print(json.dumps(Cluster(Cnf(config, creds='env')).node_pools[nodepool].get_node(int(node_number)).update(), indent=2))
