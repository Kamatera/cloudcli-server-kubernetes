import logging
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, logger, Request, APIRouter, Depends

from . import common, config, version, api


router = APIRouter()


async def get_creds(request: Request):
    return request.headers.get('AuthClientId'), request.headers.get('AuthSecret')


@router.get("/", include_in_schema=False)
async def root():
    logging.debug('Root endpoint called')
    return {"ok": True}


@router.post('/create_cluster')
async def create_cluster(config_: str, creds: tuple = Depends(get_creds)):
    return {
        'command_id': api.create_cluster(common.parse_config(config_), creds=creds)
    }


@router.post('/add_worker')
async def add_worker(config_: str, nodepool_name: str, node_number: int, creds: tuple = Depends(get_creds)):
    return {
        'command_id': api.add_worker(common.parse_config(config_), nodepool_name, node_number, creds=creds)
    }


@router.post('/status')
async def status(config_: str, full: bool = False, creds: tuple = Depends(get_creds)):
    return api.cluster_status(common.parse_config(config_), full, creds=creds)


@asynccontextmanager
async def lifespan(app_):
    common.setup_logging(handlers=logger.logger.handlers)
    app_.include_router(router, prefix='/k8s')
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
