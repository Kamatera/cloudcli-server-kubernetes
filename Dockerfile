# Pulled Oct 18, 2024
ARG BASE_IMAGE=python:3.12@sha256:5db6b270780fa20e04545877473e81d0b74cf35614d6002247c5e73453d79e8c

FROM $BASE_IMAGE as base
WORKDIR /srv
RUN curl -LsSf https://astral.sh/uv/0.6.14/install.sh | XDG_BIN_HOME=/usr/local/bin sh
COPY pyproject.toml uv.lock ./
RUN uv export --no-dev --no-emit-project > requirements.txt

FROM $BASE_IMAGE
WORKDIR /srv
COPY --from=base /srv/requirements.txt ./
RUN pip install -r requirements.txt
COPY pyproject.toml README.md LICENSE gunicorn_conf.py entrypoint.sh ./
COPY cloudcli_server_kubernetes ./cloudcli_server_kubernetes
RUN pip install -e .
ARG VERSION=docker-local-development
RUN echo VERSION = "'$VERSION'" > cloudcli_server_kubernetes/version.py
ENV PYTHONUNBUFFERED=1
ENV MAX_WORKERS=4
ENV TZ=UTC
ENTRYPOINT ["./entrypoint.sh"]
