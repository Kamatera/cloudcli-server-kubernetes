# Pulled Oct 18, 2024
FROM python:3.12@sha256:5db6b270780fa20e04545877473e81d0b74cf35614d6002247c5e73453d79e8c
WORKDIR /srv
RUN pip install --upgrade pip poetry
COPY gunicorn_conf.py ./
COPY pyproject.toml poetry.lock ./
RUN poetry export > requirements.txt
RUN pip install -r requirements.txt
RUN mkdir cloudcli_server_kubernetes && touch cloudcli_server_kubernetes/__init__.py && touch README.md
RUN pip install -e .
COPY cloudcli_server_kubernetes ./cloudcli_server_kubernetes
ARG VERSION=docker-local-development
RUN echo VERSION = "'$VERSION'" > cloudcli_server_kubernetes/version.py
ENV PYTHONUNBUFFERED=1
ENV MAX_WORKERS=4
ENV TZ=UTC
COPY entrypoint.sh ./
ENTRYPOINT ["./entrypoint.sh"]
