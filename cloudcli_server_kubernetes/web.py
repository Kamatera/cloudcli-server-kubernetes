import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, logger, Request, APIRouter, Depends, Form

from . import common, config, version, tasks


router = APIRouter()


def get_openapi_extra(use, short, flags=None, long=None, wait=False, kconfig=True, extra_run=None):
    flags = flags or []
    extra_run = extra_run or {
        "ComplexJsonServerResponse": True,
    }
    command = {
        "use": use,
        "short": short,
        "long": f"{short}\n\n{long}" if long else short,
        "flags": flags,
        "run": {
            "cmd": "post",
            "path": f"/k8s/{use}",
            "method": "post",
            **extra_run
        }
    }
    if kconfig:
        command["flags"] = [
            {
                "name": "kconfig",
                "required": True,
                "usage": "Path to Kamatera cluster configuration file in JSON or YAML format\nUse our server configuration interface at https://kamatera.github.io/kamateratoolbox/serverconfiggen_k8s.html to generate this configuration file",
            },
            *command["flags"]
        ]
    if wait:
        command["wait"] = True
        command["flags"] += [{
            "name": "wait",
            "usage": "Wait for command execution to finish only then exit cli.",
            "bool": True,
            "processing": [
                {
                    "method": "validateAllowedOutputFormats",
                    "args": ["human"]
                }
            ]
        }]
    command["run"]["fields"] = [{"name": f["name"], "flag": f["name"]} for f in flags]
    if kconfig:
        command["run"]["fields"] = [
            {
                "name": "kconfig",
                "flag": "kconfig",
                "fromFile": True,
            },
            *command["run"]["fields"]
        ]
    return {
        "x-cloudcli-k8s": command,
    }


async def get_creds(request: Request):
    return request.headers.get('AuthClientId'), request.headers.get('AuthSecret')


@router.get("/k8s/", include_in_schema=False)
async def root():
    logging.debug('Root endpoint called')
    return {"ok": True}


@router.post('/k8s/task_status', openapi_extra=get_openapi_extra(
    "task_status",
    "Get task status",
    [
        {
            "name": "task_id",
            "required": True,
            "usage": "Task ID",
        }
    ],
    kconfig=False
))
async def task_status(task_id: str = Form(), creds: tuple = Depends(get_creds)):
    return common.IndentedJSONResponse(common.get_task_status(task_id, creds))


@router.post('/k8s/create_cluster', openapi_extra=get_openapi_extra(
    "create_cluster",
    "Create a Kubernetes cluster (BETA)",
    long="Create a new cluster or create all node pools / nodes in an existing cluster.\nSafe to run multiple times, only new nodes will be created and added to the relevant node pools in the cluster."
))
async def create_cluster(kconfig: str = Form(), creds: tuple = Depends(get_creds)):
    return {
        "task_id": tasks.create_cluster.delay(kconfig, creds).id
    }


@router.post('/k8s/create_nodepool', openapi_extra=get_openapi_extra(
    "create_nodepool",
    "Create a nodepool (BETA)",
    [
        {
            "name": "nodepool_name",
            "required": True,
            "usage": "Nodepool name",
        },
    ],
    long="Create a new nodepool in an existing cluster or create additional nodes in an existing nodepool.\nSafe to run multiple times, only new nodes will be created and added to the nodepool."
))
async def create_nodepool(kconfig: str = Form(), nodepool_name: str = Form(), creds: tuple = Depends(get_creds)):
    return {
        "task_id": tasks.create_nodepool.delay(kconfig, nodepool_name, creds).id
    }


@router.post('/k8s/create_node', openapi_extra=get_openapi_extra(
    "create_node",
    "Create a node (BETA)",
    [
        {
            "name": "nodepool_name",
            "required": True,
            "usage": "Nodepool name",
        },
        {
            "name": "node_number",
            "required": True,
            "usage": "Node number",
        },
    ],
    long="Create a new node in an existing nodepool.\nSafe to run multiple times, the node will be added only if it does not already exist in the nodepool."
))
async def create_node(kconfig: str = Form(), nodepool_name: str = Form(), node_number: str = Form(), creds: tuple = Depends(get_creds)):
    return {
        "task_id": tasks.create_node.delay(kconfig, nodepool_name, node_number, creds).id
    }


@router.post('/k8s/update_cluster', openapi_extra=get_openapi_extra(
    "update_cluster",
    "Update a Kubernetes cluster (BETA)",
    long="Update an existing cluster and all node-pools and nodes - in case of configuration changes. Does not cause down-time."
))
async def update_cluster(kconfig: str = Form(), creds: tuple = Depends(get_creds)):
    return {
        "task_id": tasks.update_cluster.delay(kconfig, creds).id
    }


@router.post('/k8s/update_nodepool', openapi_extra=get_openapi_extra(
    "update_nodepool",
    "Update a nodepool (BETA)",
    [
        {
            "name": "nodepool_name",
            "required": True,
            "usage": "Nodepool name",
        },
    ],
    long="Update an existing nodepool and all it's nodes - in case of configuration changes. Does not cause down-time."
))
async def update_nodepool(kconfig: str = Form(), nodepool_name: str = Form(), creds: tuple = Depends(get_creds)):
    return {
        "task_id": tasks.update_nodepool.delay(kconfig, nodepool_name, creds).id
    }


@router.post('/k8s/update_node', openapi_extra=get_openapi_extra(
    "update_node",
    "Update a node (BETA)",
    [
        {
            "name": "nodepool_name",
            "required": True,
            "usage": "Nodepool name",
        },
        {
            "name": "node_number",
            "required": True,
            "usage": "Node number",
        },
    ],
    long="Update a single node - in case of configuration changes. Does not cause down-time."
))
async def update_node(kconfig: str = Form(), nodepool_name: str = Form(), node_number: str = Form(), creds: tuple = Depends(get_creds)):
    return {
        "task_id": tasks.update_node.delay(kconfig, nodepool_name, node_number, creds).id
    }


@router.post('/k8s/status', openapi_extra=get_openapi_extra(
    "status",
    "Get Kubernetes cluster status (BETA)",
    long="Get the status of the cluster and all it's node-pools and nodes."
))
async def status(kconfig: str = Form(), creds: tuple = Depends(get_creds)):
    return {
        "task_id": tasks.get_cluster_status.delay(kconfig, creds).id
    }


@router.post('/k8s/kubeconfig', openapi_extra=get_openapi_extra(
    "kubeconfig",
    "Get cluster kubeconfig (BETA)",
    long="Get the kubeconfig file for the cluster."
))
async def status(kconfig: str = Form(), creds: tuple = Depends(get_creds)):
    return {
        "task_id": tasks.get_kubeconfig.delay(kconfig, creds).id
    }


@asynccontextmanager
async def lifespan(app_):
    common.setup_logging(handlers=logger.logger.handlers)
    app_.include_router(router)
    logging.info('App initialized')
    schema = app.openapi()
    schema['components']["securitySchemes"] = {
        "APIKeyHeader": {
            "type": "apiKey",
            "in": "header",
            "name": "AuthClientId",
        },
        "APISecretHeader": {
            "type": "apiKey",
            "in": "header",
            "name": "AuthSecret",
        },
    }
    schema["security"] = [
        {"APIKeyHeader": [], "APISecretHeader": []}
    ]
    try:
        yield
    finally:
        logging.info('App shutting down')
        logging.shutdown()


async def global_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, common.CloudcliException):
        message = str(exc)
    else:
        message = "Internal Server Error. Please try again later."
    content = {
        "message": message,
    }
    if config.CLOUDCLI_DEBUG:
        content.update({
            "exception": str(exc),
            # "traceback": traceback.format_exception(exc),
        })
    return common.IndentedJSONResponse(
        status_code=500,
        content=content,
    )


app = FastAPI(
    version=version.VERSION,
    title='Kamatera Cloud CLI Kubernetes',
    lifespan=lifespan,
    docs_url='/k8s/docs',
    openapi_url='/k8s/openapi.json',
)
app.add_exception_handler(Exception, global_exception_handler)
