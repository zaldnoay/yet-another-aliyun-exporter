FROM python:3.9 as builder

    # python
ENV PYTHONUNBUFFERED=1 \
    # prevents python creating .pyc files
    PYTHONDONTWRITEBYTECODE=1 \
    # pip
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=60 \
    # do not ask any interactive question
    POETRY_NO_INTERACTION=1 \
    # paths
    # this is where our requirements + virtual environment will live
    APP_PATH="/srv/ali-exporter/"

WORKDIR $APP_PATH

COPY . .

RUN apt-get update && \
    apt-get install --no-install-recommends -y \
        # deps for building python deps
        build-essential
RUN pip install poetry
RUN poetry export --without-hashes > requirements.txt

FROM python:3.9-slim

ENV APP_PATH="/srv/ali-exporter/" \
    POETRY_NO_INTERACTION=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=60

COPY --from=builder $APP_PATH $APP_PATH

WORKDIR ${APP_PATH}

RUN pip install -r requirements.txt
RUN apt-get update && \
    apt-get install -y --no-install-recommends tini && \
    rm -rf /var/lib/apt/lists/*

ENTRYPOINT [ "/usr/bin/tini", "--", "python", "-m", "aliyun_exporter" ]
CMD ["-c", "/srv/ali-exporter/config/aliyun.yaml"]
