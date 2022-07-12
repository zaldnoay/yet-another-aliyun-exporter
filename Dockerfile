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
    POETRY_NO_INTERACTION=1

WORKDIR /srv/ali-exporter/
COPY pyproject.toml poetry.lock ./

RUN apt-get update && \
    apt-get install --no-install-recommends -y \
        # deps for building python deps
        build-essential
RUN pip install poetry
RUN poetry export --without-hashes > requirements.txt
RUN python -m venv /srv/ali-exporter/venv && \
    . ./venv/bin/activate && \
    pip install -r requirements.txt

FROM python:3.9-slim

WORKDIR /srv/ali-exporter/
COPY --from=builder /srv/ali-exporter/venv ./venv
COPY . .

ENV PATH /srv/ali-exporter/venv/bin:$PATH

RUN apt-get update && \
    apt-get install -y --no-install-recommends tini && \
    rm -rf /var/lib/apt/lists/*

ENTRYPOINT [ "/usr/bin/tini", "--" ]
CMD ["python", "-m", "aliyun_exporter", "-c", "/srv/ali-exporter/config/aliyun.yaml"]
