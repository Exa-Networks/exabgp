# syntax=docker/dockerfile:1.4

# for example, the configuration is generated from within the dockerfile
# but COPY can be used

# build an exabgp docker image called exabgp using the code in the current folder
# docker build -t exabgp ./

# run the created container, mapping the BGP port for remote access
# use the container like you would use the exabgp binary
# docker run -p 179:1790 -it exabgp server -v /etc/exabgp/exabgp.conf

# you can use a local configuration file bind mounting the folder
# change source for the folder with your configuration files
# docker run -p 179:1790 --mount type=bind,source=`pwd`/etc/exabgp,target=/etc/exabgp -it exabgp -v /etc/exabgp/parse-simple-v4.conf

# debug changes to the dockerfile with
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

COPY <<EOF /opt/exabgp/src/exabgp/application/etc/exabgp/exabgp.env
[exabgp.api]
ack = true
chunk = 1
cli = true
compact = false
encoder = json
pipename = 'exabgp'
respawn = true
terminate = false

[exabgp.bgp]
openwait = 60
passive = false

[exabgp.cache]
attributes = true
nexthops = true

[exabgp.daemon]
daemonize = false
drop = true
pid = ''
umask = '0o137'
user = 'exa'

[exabgp.log]
all = false
configuration = true
daemon = true
destination = 'stdout'
enable = true
level = INFO
message = false
network = true
packets = false
parser = false
processes = true
reactor = true
rib = false
routes = false
short = true
timers = false

[exabgp.pdb]
enable = false

[exabgp.profile]
enable = false
file = ''

[exabgp.reactor]
speed = 1.0

[exabgp.tcp]
acl = false
bind = ''
delay = 0
once = false
port = 179
EOF

ENV PYTHONPATH=/opt/exabgp/src
# ENTRYPOINT [ "/bin/bash"]
ENTRYPOINT [ \
    "/usr/bin/dumb-init", "--", \ 
    "python3", "/opt/exabgp/src/exabgp/application/main.py" \
]
