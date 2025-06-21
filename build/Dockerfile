ARG BASEIMAGE
FROM ${BASEIMAGE}

ARG BASE_TYPE
ENV BASE_TYPE=${BASE_TYPE}

WORKDIR /usr/src

RUN apt-get update && \
    if [ "$BASE_TYPE" = "cuda" ]; then \
      apt-get install -y --no-install-recommends \
        build-essential \
        python3 \
        python3-dev \
        python3-pip \
        netcat-traditional; \
    else \
      apt-get install -y --no-install-recommends \
        build-essential \
        netcat-traditional; \
    fi

RUN pip3 install --no-cache-dir --upgrade pip
RUN pip3 install --no-cache-dir --upgrade \
        setuptools \
        wheel

WORKDIR /
COPY requirements.txt ./
RUN ls -lah
RUN pip3 install --no-cache-dir -r requirements.txt

RUN pip3 install --no-cache-dir whispywyser


RUN pip3 install --no-cache-dir -U --upgrade wyoming faster-whisper

RUN apt-get purge -y --auto-remove build-essential python3-dev
RUN rm -rf /var/lib/apt/lists/*

WORKDIR /
COPY build/docker-entrypoint.sh ./


LABEL org.opencontainers.image.source="https://github.com/cociweb/WhispyWyser"

EXPOSE 10300
ENTRYPOINT ["bash", "/docker-entrypoint.sh"]

HEALTHCHECK --interval=30s --timeout=3s --start-period=30s \
        CMD echo '{ "type": "describe" }' \
        | nc -w 1 localhost 10300 \
        | grep -q "faster-whisper" \
        || exit 1
