FROM python:3

RUN mkdir -p /src
COPY setup.py /src
COPY CHANGELOG /src
COPY debian/ /src
# COPY etc/ /src/etc
COPY lib/ /src/lib/
# COPY qa/ /src/qa

RUN pip install --upgrade pip setuptools
RUN cd /src && pip install .

RUN rm -rf /src

CMD ["exabgp", "--help"]
