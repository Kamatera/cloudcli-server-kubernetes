import time
import json
import logging
import traceback

from fastapi.responses import JSONResponse

from . import config


class CloudcliException(Exception):
    pass


def setup_logging(**kwargs):
    logging.basicConfig(level=getattr(logging, config.LOG_LEVEL), **kwargs)


class IndentedJSONResponse(JSONResponse):

    def render(self, content) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            separators=(",", ":"),
        ).encode("utf-8")


def wait_task_status(task_id, creds):
    task_status = get_task_status(task_id, creds)
    while task_status['state'] == 'PENDING':
        time.sleep(5)
        task_status = get_task_status(task_id, creds)
        print('.')
    return task_status


def get_task_status(task_id, creds):
    from .celery import app
    if creds == 'env':
        creds = (config.KAMATERA_API_CLIENT_ID, config.KAMATERA_API_SECRET)
    try:
        r = app.AsyncResult(task_id)
        logging.debug(f'got task status result: {r.result.__class__}')
        if isinstance(r.result, CloudcliException) or (isinstance(r.result, Exception) and r.result.__class__.__name__ == 'CnfConfigError'):
            return {
                'task_id': r.id,
                'task_name': None,
                'state': 'FAILURE',
                'result': None,
                'error': str(r.result),
                'meta': {}
            }
        elif r.result:
            result = CeleryRunnerResult.parse(r.result, creds)
            if isinstance(result, CeleryRunnerResult) and r.state == 'SUCCESS':
                return {
                    'task_id': r.id,
                    **result.get_task_status()
                }
            else:
                return {
                    'task_id': r.id,
                    'task_name': None,
                    'state': r.state,
                    'result': result,
                    'error': 'An unexpected error occurred, please try again later' if r.state == 'FAILURE' else None,
                    'meta': {}
                }
        else:
            return {
                'task_id': r.id,
                'task_name': None,
                'state': 'PENDING',
                'result': None,
                'error': None,
                'meta': {}
            }
    except Exception as e:
        raise Exception(f'failed to get task status for task_id {task_id}: {e}') from e


class CeleryRunnerResult:
    object_name = 'common'

    def __init__(self, task_name, result, creds, error=None, tb=None, meta=None):
        self.task_name = task_name
        self.result = result
        self.creds = creds
        self.error = error
        self.traceback = tb
        self.meta = meta

    def export(self):
        if callable(self.result):
            try:
                self.result = self.result()
            except Exception as e:
                self.result = None
                self.error = str(e) if isinstance(e, CloudcliException) else 'An unexpected error occurred, please try again later'
                self.traceback = traceback.format_exc()
        return {
            '__result_type': 'CeleryRunnerResult',
            'object_name': self.object_name,
            'task_name': self.task_name,
            'result': self.result,
            'error': self.error,
            'traceback': self.traceback,
            'creds': self.creds,
            'meta': self.meta,
        }

    @classmethod
    def parse(cls, result, creds):
        logging.debug(f'parsing result: {result} / {creds}')
        if isinstance(result, dict) and result.get('__result_type') == 'CeleryRunnerResult':
            object_name = result.get('object_name')
            task_name = result.get('task_name')
            result_creds = result.get('creds')
            result_result = result.get('result')
            result_error = result.get('error')
            result_traceback = result.get('traceback')
            result_meta = result.get('meta')
            if object_name and task_name and result_creds:
                if result_creds != creds:
                    raise CloudcliException(f'invalid result')
                resultargs = (task_name, result_result, creds, result_error, result_traceback, result_meta)
                if object_name == 'cluster':
                    from .lib.cluster import ClusterCeleryRunnerResult
                    return ClusterCeleryRunnerResult(*resultargs)
                elif object_name == 'nodepool':
                    from .lib.nodepool import NodePoolCeleryRunnerResult
                    return NodePoolCeleryRunnerResult(*resultargs)
                elif object_name == 'common':
                    return cls(*resultargs)
        if creds is not None:
            raise CloudcliException(f'invalid result')
        return result

    def get_task_status_meta(self):
        return self.meta or {}

    def get_task_status(self):
        if self.result:
            state = 'SUCCESS'
        elif self.error:
            state = 'FAILURE'
        else:
            state = 'PENDING'
        return {
            'task_name': self.task_name,
            'state': state,
            'result': self.result,
            'error': self.error,
            'meta': self.get_task_status_meta(),
        }

    def get_multi_tasks_status(self, task_name, task_ids=None):
        state = 'PENDING'
        result = None
        error = None
        meta = self.get_task_status_meta()
        task_ids = task_ids or []
        task_statuses = meta['subtasks'] = [get_task_status(task_id, self.creds) for task_id in task_ids]
        if self.error:
            state = 'FAILURE'
            error = self.error
        if len(task_statuses) == 0 or all(task_status['state'] == 'SUCCESS' for task_status in task_statuses):
            state = 'SUCCESS'
            result = [task_status['result'] for task_status in task_statuses]
        elif not any(task_status['state'] == 'PENDING' for task_status in task_statuses) and any(task_status['state'] == 'FAILURE' for task_status in task_statuses):
            state = 'FAILURE'
            error = 'Some sub-tasks failed'
        return {
            'task_name': task_name,
            'state': state,
            'result': result,
            'error': error,
            'meta': meta,
        }
