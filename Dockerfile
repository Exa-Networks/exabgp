# syntax=docker/dockerfile:1.4

# how to build and run exabgp using docker (using the local copy)
# this dockerfile install exabgp in the container /opt

# docker build -t exabgp-main ./
# docker run -p 179:1790 --mount type=bind,source=`pwd`/etc/exabgp,target=/etc/exabgp exabgp-main version
# docker run -it exabgp-main version

# debug the build
# docker build --progress=plain --no-cache -t exabgp ./

FROM python:3-slim-buster

# update packages
RUN apt update
RUN apt -y dist-upgrade
RUN apt install -y dumb-init
RUN rm -rf /var/lib/apt/lists/* /var/cache/apt/*

# Add ExaBGP
ADD . /opt/exabgp
RUN useradd -r exa
RUN mkdir /etc/exabgp
RUN mkfifo /run/exabgp.in
RUN mkfifo /run/exabgp.out
RUN chown exa /run/exabgp.in
RUN chown exa /run/exabgp.out
RUN chmod 600 /run/exabgp.in
RUN chmod 600 /run/exabgp.out

RUN echo "[exabgp.daemon]" > /opt/exabgp/etc/exabgp/exabgp.env
RUN echo "user = 'exa'" >> /opt/exabgp/etc/exabgp/exabgp.env

ENV PYTHONPATH=/opt/exabgp/src
ENV PATH=$PATH:/opt/exabgp/sbin/

# ENTRYPOINT [ "/bin/bash"]
ENTRYPOINT [ \
    "/usr/bin/dumb-init", "--", \ 
    "/opt/exabgp/sbin/exabgp" \
]
