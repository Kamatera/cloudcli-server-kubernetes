import typing
from functools import partial

import celery
from celery.result import AsyncResult, GroupResult

from .node import Node, NodeException
from .. import common

if typing.TYPE_CHECKING:
    from .cluster import Cluster


class NodePool:

    def __init__(self, cluster: 'Cluster', name: str):
        self.name = name
        self.cluster = cluster

    def get_celery_runner(self):
        return NodePoolCeleryRunner(self)

    def node_numbers(self) -> list[int]:
        return self.cluster.cnf.node_pools[self.name].nodes

    def get_node(self, node_number) -> Node:
        if node_number not in self.node_numbers():
            raise NodeException(f'Node {node_number} not found in nodepool {self.name}')
        return Node(self, node_number)

    @property
    def node_pool_config(self) -> dict:
        return self.cluster.cnf.node_pools[self.name].node_pool_config

    def get_create_celery_group(self):
        if self.name == 'controlplane':
            raise NodeException('to create controlplane nodes, run create cluster or create a specific controlplane node')
        return celery.group(
            self.get_node(node_number).get_create_celery_signature()
            for node_number in self.node_numbers()
        )

    def get_update_celery_group(self):
        if self.name == 'controlplane':
            raise NodeException('to update controlplane nodes, run update cluster or update a specific controlplane node')
        return celery.group(
            self.get_node(node_number).get_update_celery_signature()
            for node_number in self.node_numbers()
        )


class NodePoolCeleryRunner:

    def __init__(self, nodepool):
        self.nodepool = nodepool

    def create(self, task: celery.Task):
        from cloudcli_server_kubernetes.tasks import create_node
        return NodePoolCeleryRunnerResult(
            'create', partial(self.create_update, task, create_node), self.nodepool.cluster.cnf.creds,
            meta={
                'nodepool_name': self.nodepool.name
            }
        ).export()

    def update(self, task: celery.Task):
        from cloudcli_server_kubernetes.tasks import update_node
        return NodePoolCeleryRunnerResult(
            'update', partial(self.create_update, task, update_node), self.nodepool.cluster.cnf.creds,
            meta={
                'nodepool_name': self.nodepool.name
            }
        ).export()

    def create_update(self, task: celery.Task, create_update_task):
        cnf = self.nodepool.cluster.cnf.export()
        if self.nodepool.name == 'controlplane':
            first_server_result: AsyncResult = create_update_task.si(cnf, 'controlplane', 1).delay()
            other_servers_group_result: GroupResult = celery.group(
                create_update_task.si(cnf, 'controlplane', node_number)
                for node_number in self.nodepool.node_numbers()
                if node_number != 1
            ).delay()
            return {
                'nodepool_name': self.nodepool.name,
                'first_node_task_id': first_server_result.id,
                'other_nodes_task_ids': [c.id for c in other_servers_group_result.children]
            }
        else:
            servers_group_result: GroupResult = celery.group(
                create_update_task.si(cnf, self.nodepool.name, node_number)
                for node_number in self.nodepool.node_numbers()
            ).delay()
            return {
                'nodepool_name': self.nodepool.name,
                'nodes_task_ids': [c.id for c in servers_group_result.children]
            }


class NodePoolCeleryRunnerResult(common.CeleryRunnerResult):
    object_name = 'nodepool'

    def get_task_status_meta(self):
        return {**self.meta, **self.result}

    def get_task_status(self):
        assert self.task_name in ['create', 'update']
        task_ids = []
        if not self.error:
            if self.result['nodepool_name'] == 'controlplane':
                task_ids = [self.result['first_node_task_id'], *self.result['other_nodes_task_ids']]
            else:
                task_ids = self.result['nodes_task_ids']
        return self.get_multi_tasks_status(
            f'{self.task_name}_nodepool',
            task_ids
        )
