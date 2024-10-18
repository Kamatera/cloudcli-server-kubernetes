#!/usr/bin/env bash

exec gunicorn -k uvicorn.workers.UvicornWorker -c gunicorn_conf.py "cloudcli_server_kubernetes.web:app"
