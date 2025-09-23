# syntax=docker/dockerfile:1.4

# how to build and run exabgp using docker (using the local copy)
# this dockerfile install exabgp in the container /opt

# docker build -t exabgp-main ./
# docker run -p 179:1790 --mount type=bind,source=`pwd`/etc/exabgp,target=/etc/exabgp exabgp-main version
# docker run -it exabgp-main version
# docker run -it exabgp-main etc/exabgp/exabgp.conf

# debug the build
# docker build --progress=plain --no-cache -t exabgp ./

FROM python:3.13-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /build

COPY . /build/

# Build application wheel
RUN uv build --wheel

# Install the application into /app
RUN pip install --target /opt/exabgp dist/*.whl


FROM python:3.13-slim-bookworm
#COPY --from=builder /env /env
COPY --from=builder /opt/exabgp /opt/exabgp
ENV PYTHONPATH=/opt/exabgp
ENV PATH=/opt/exabgp/bin:$PATH

# install deps
RUN apt-get update \
    && apt-get install -y iproute2 dumb-init \
    && apt-get clean

# Add ExaBGP
RUN useradd -r exa \
    && mkdir /etc/exabgp \
    && mkfifo /run/exabgp.in \
    && mkfifo /run/exabgp.out \
    && chown exa /run/exabgp.in \
    && chown exa /run/exabgp.out \
    && chmod 600 /run/exabgp.in \
    && chmod 600 /run/exabgp.out

RUN echo "[exabgp.daemon]" > /opt/exabgp/etc/exabgp/exabgp.env \
    && echo "user = 'exa'" >> /opt/exabgp/etc/exabgp/exabgp.env

ENTRYPOINT [ \
    "/usr/bin/dumb-init", "--", \
    "exabgp" \
]
