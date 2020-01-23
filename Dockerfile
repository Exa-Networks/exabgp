FROM python:3

RUN mkdir -p /src
COPY setup.py /src
COPY CHANGELOG.rst /src
COPY debian/ /src
COPY lib/ /src/lib/

RUN pip install --upgrade pip setuptools
RUN cd /src && pip install .

RUN rm -rf /src

CMD ["exabgp", "--help"]
