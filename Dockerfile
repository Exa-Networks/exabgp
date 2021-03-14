FROM python:3-slim-buster

ARG version="master"
ENV PYTHONPATH "/tmp/exabgp/src"

RUN apt update \
    && apt -y dist-upgrade \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/*

ADD . /tmp/exabgp
WORKDIR /tmp/exabgp
RUN ln -s src/exabgp exabgp

# RUN python3 -c "import exabgp.application.main; exabgp.application.main.main()"
RUN echo Building exabgp ${version}
RUN pip3 install --upgrade pip setuptools wheel
RUN pip3 install .
WORKDIR /usr/local/etc/exabgp
