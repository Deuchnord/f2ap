FROM python:3.11

MAINTAINER "Jérôme Deuchnord <jerome@deuchnord.fr>"

ENV LOG_LEVEL=INFO

EXPOSE 80

WORKDIR /data

COPY config.toml.dist config.toml

WORKDIR /usr/src/app

COPY f2ap ./f2ap
COPY README.md .
COPY pyproject.toml .
COPY poetry.lock .

RUN pip install --no-cache-dir poetry && \
    poetry build && \
    pip install --user ./dist/f2ap*.whl && \
    rm -rf /usr/src/app/*

CMD python -m f2ap --config=/data/config.toml --log-level=${LOG_LEVEL} --port=80
