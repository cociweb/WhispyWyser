ARG BASEIMAGE
FROM ${BASEIMAGE}


ARG WYOMING_FASTER_WHISPER_VERSION=2.5.0
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

RUN pip3 install --no-cache-dir -U  --upgrade pip
RUN pip3 install --no-cache-dir -U \
        setuptools \
        wheel

WORKDIR /
ADD https://github.com/rhasspy/wyoming-faster-whisper/archive/refs/tags/v${WYOMING_FASTER_WHISPER_VERSION}.tar.gz wyoming_faster_whisper-${WYOMING_FASTER_WHISPER_VERSION}.tar.gz
RUN ls -lah
RUN pip3 install --no-cache-dir wyoming_faster_whisper-${WYOMING_FASTER_WHISPER_VERSION}.tar.gz

RUN if [ "$BASE_TYPE" = "cuda" ]; then \
      METADATA_DIR="/usr/local/lib/python3.12/dist-packages/wyoming_faster_whisper-${WYOMING_FASTER_WHISPER_VERSION}.dist-info"; \
    else \
      METADATA_DIR="/usr/local/lib/python3.12/site-packages/wyoming_faster_whisper-${WYOMING_FASTER_WHISPER_VERSION}.dist-info"; \
    fi && \
    cd "$METADATA_DIR" && \
    ls -lah && \
    sed -i -e 's/wyoming==1.5.3/wyoming>=1.6.1/g' \
       -e 's/faster-whisper==1.1.0/faster-whisper>=1.1.1/g' METADATA;

RUN pip3 install --no-cache-dir -U --upgrade wyoming faster-whisper

RUN apt-get purge -y --auto-remove build-essential python3-dev
RUN rm -rf /var/lib/apt/lists/*

WORKDIR /
COPY WhispyWyser/common/docker-entrypoint.sh ./

#RUN if [ "$BASE_TYPE" = "cuda" ]; then \
#      cd /usr/local/lib/python3.10/dist-packages/wyoming_faster_whisper/; \
#    else \
#      cd /usr/local/lib/python3.11/site-packages/wyoming_faster_whisper/; \
#    fi
#
#
#COPY WhispyWyser/common/replacables ./

LABEL org.opencontainers.image.source="https://github.com/cociweb/WhispyWyser"

EXPOSE 10300
ENTRYPOINT ["bash", "/docker-entrypoint.sh"]

HEALTHCHECK --interval=30s --timeout=3s --start-period=30s \
        CMD echo '{ "type": "describe" }' \
        | nc -w 1 localhost 10300 \
        | grep -q "faster-whisper" \
        || exit 1
