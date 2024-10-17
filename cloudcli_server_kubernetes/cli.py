import os
import json
import click
import subprocess

from . import api, common


def wait_command(command_id):
    from . import config
    print(f'Command ID: {command_id}')
    subprocess.check_call([
        'cloudcli', 'queue', 'detail', '--id', str(command_id), '--wait'
    ], env={
        **os.environ,
        'CLOUDCLI_APISERVER': config.KAMATERA_API_SERVER,
        'CLOUDCLI_APICLIENTID': config.KAMATERA_API_CLIENT_ID,
        'CLOUDCLI_APISECRET': config.KAMATERA_API_SECRET
    })


@click.group()
def main():
    pass


@main.command()
@click.argument('config')
def create(config):
    command_id = api.create_cluster(common.parse_config(config))
    if command_id:
        wait_command(command_id)
    else:
        print('Cluster Created')


@main.command()
@click.argument('config')
@click.argument('nodepool_name')
@click.argument('node_number')
def add_worker(config, nodepool_name, node_number):
    command_id = api.add_worker(common.parse_config(config), nodepool_name, node_number)
    if command_id:
        wait_command(command_id)
    else:
        print('Server Already Exists')


@main.command()
@click.argument('config')
@click.option('--full', is_flag=True)
def status(config, full):
    print(json.dumps(api.cluster_status(common.parse_config(config), full), indent=2))
