# cloudcli-server-kubernetes

Python CLI, API and Web App for managing Kamatera Kubernetes Clusters

## Local Development

```
poetry install
```

Create a `.env` file with the following content:

```
KAMATERA_API_CLIENT_ID=
KAMATERA_API_SECRET=
```

Start the infrastructure:

```
docker compose up -d db rabbitmq
```

Start a Celery worker:

```
celery -A cloudcli_server_kubernetes.celery worker --loglevel info
```

Create the cluster configuration file, you can use the example `tests/cluster_full.yaml`, just change the cluster name

Create the cluster:

```
poetry run cloudclik8s cluster create cluster.yaml --wait
```

See more available commands in the cli:

```
poetry run cloudclik8s --help
```

Run the Web app:

```
poetry run uvicorn cloudcli_server_kubernetes.web:app --reload
```

Access the API Docs at http://localhost:8000/docs

## Local Development with Docker

Start the full environment:

```
docker compose up -d
```

Access the API Docs at http://localhost:8080/docs
