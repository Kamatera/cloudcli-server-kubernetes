import logging

from .celery import app


@app.task(name='create_cluster', bind=True)
def create_cluster(task, cnf, creds=None):
    logging.debug(f'create_cluster {cnf}')
    from .lib.cluster import ClusterCeleryRunner
    return ClusterCeleryRunner.init_from_cnf_creds(cnf, creds).create(task)


@app.task(name='create_nodepool', bind=True)
def create_nodepool(task, cnf, nodepool_name, creds=None):
    logging.debug(f'create_nodepool {cnf} {nodepool_name}')
    from .lib.cluster import ClusterCeleryRunner
    return ClusterCeleryRunner.init_from_cnf_creds(cnf, creds).get_nodepool_celery_runner(nodepool_name).create(task)


@app.task(name='create_node', bind=True)
def create_node(task, cnf, nodepool_name, node_number, creds=None):
    logging.debug(f'create_node {cnf} {nodepool_name} {node_number}')
    from .lib.cluster import ClusterCeleryRunner
    return ClusterCeleryRunner.init_from_cnf_creds(cnf, creds).get_node_celery_runner(nodepool_name, node_number).create(task)


@app.task(name='update_cluster', bind=True)
def update_cluster(task, cnf, creds=None):
    logging.debug(f'update_cluster {cnf}')
    from .lib.cluster import ClusterCeleryRunner
    return ClusterCeleryRunner.init_from_cnf_creds(cnf, creds).update(task)


@app.task(name='update_nodepool', bind=True)
def update_nodepool(task, cnf, nodepool_name, creds=None):
    logging.debug(f'update_nodepool {cnf} {nodepool_name}')
    from .lib.cluster import ClusterCeleryRunner
    return ClusterCeleryRunner.init_from_cnf_creds(cnf, creds).get_nodepool_celery_runner(nodepool_name).update(task)


@app.task(name='update_node', bind=True)
def update_node(task, cnf, nodepool_name, node_number, creds=None):
    logging.debug(f'update_node {cnf} {nodepool_name} {node_number}')
    from .lib.cluster import ClusterCeleryRunner
    return ClusterCeleryRunner.init_from_cnf_creds(cnf, creds).get_node_celery_runner(nodepool_name, node_number).update(task)


@app.task(name='get_cluster_status', bind=True)
def get_cluster_status(task, cnf, creds=None):
    logging.debug(f'get_cluster_status {cnf}')
    from .lib.cluster import ClusterCeleryRunner
    return ClusterCeleryRunner.init_from_cnf_creds(cnf, creds).get_cluster_status(task)


@app.task(name='get_kubeconfig', bind=True)
def get_kubeconfig(task, cnf, creds=None):
    logging.debug(f'get_kubeconfig {cnf}')
    from .lib.cluster import ClusterCeleryRunner
    return ClusterCeleryRunner.init_from_cnf_creds(cnf, creds).get_kubeconfig(task)
