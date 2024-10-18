import logging
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, logger, Request, APIRouter, Depends, Form

from . import common, config, version, api


router = APIRouter()


def get_openapi_extra(use, short, flags=None, long=None, wait=False, kconfig=True):
    flags = flags or []
    command = {
        "use": use,
        "short": short,
        "long": long or short,
        "flags": flags,
        "run": {
            "cmd": "post",
            "path": f"/k8s/{use}",
            "method": "post",
        }
    }
    if kconfig:
        command["flags"] = [
            {
                "name": "kconfig",
                "required": True,
                "usage": "Path to Kamatera cluster configuration file in JSON or YAML format",
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


@router.get("/", include_in_schema=False)
async def root():
    logging.debug('Root endpoint called')
    return {"ok": True}


@router.post('/create_cluster', openapi_extra=get_openapi_extra(
    "create_cluster",
    "Create a cluster",
    wait=True
))
async def create_cluster(kconfig: str = Form(), creds: tuple = Depends(get_creds)):
    return [
        api.create_cluster(common.parse_config(kconfig), creds=creds)
    ]


@router.post('/add_worker', openapi_extra=get_openapi_extra(
    "add_worker",
    "Add a worker node",
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
        }
    ],
    wait=True
))
async def add_worker(kconfig: str = Form(), nodepool_name: str = Form(), node_number: str = Form(), creds: tuple = Depends(get_creds)):
    return [
        api.add_worker(common.parse_config(kconfig), nodepool_name, node_number, creds=creds)
    ]


@router.post('/status', openapi_extra=get_openapi_extra(
    "status",
    "Get cluster status"
))
async def status(kconfig: str = Form(), full: bool = False, creds: tuple = Depends(get_creds)):
    return common.IndentedJSONResponse(api.cluster_status(common.parse_config(kconfig), full, creds=creds))


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
    if isinstance(exc, api.CloudcliApiException):
        message = str(exc)
    else:
        message = "Internal Server Error. Please try again later."
    content = {
        "message": message,
    }
    if config.CLOUDCLI_DEBUG:
        content.update({
            "exception": str(exc),
            "traceback": traceback.format_exception(exc),
        })
    return common.IndentedJSONResponse(
        status_code=500,
        content=content,
    )


app = FastAPI(
    version=version.VERSION,
    title='Kamatera Cloud CLI Kubernetes',
    lifespan=lifespan,
    root_path='/k8s',
)
app.add_exception_handler(Exception, global_exception_handler)
