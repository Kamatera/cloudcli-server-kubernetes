from celery import Celery

from . import config


app = Celery(
    'cloudcli-server-kubernetes',
    broker=config.CELERY_BROKER,
    backend=config.CELERY_RESULT_BACKEND,
    include=[
        'cloudcli_server_kubernetes.tasks'
    ],
    broker_connection_retry_on_startup=True,
    task_reject_on_worker_lost=True,
    task_acks_late=True,
    # must run celery beat!
    result_expires=60*60*24*14
)
