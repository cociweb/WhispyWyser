
# Build stage
ARG BASEIMAGE
FROM ${BASEIMAGE} AS builder


ARG BASE_TYPE
ENV BASE_TYPE=${BASE_TYPE}


# Install build dependencies

RUN apt-get update && \
    if [ "$BASE_TYPE" = "cuda" ]; then \
      apt-get install -y --no-install-recommends \
        git \
        cmake \
        wget \
        build-essential \
        swig \
        python3 \
        python3-dev \
        python3-pip \
        python3-venv \
        locales \
        locales-all \
        ffmpeg \
        libsndfile1 \
        netcat-traditional; \
    else \
      apt-get install -y --no-install-recommends \
        git \
        cmake \
        wget \
        build-essential \
        swig \
        python3-dev \
        python3-pip \
        python3-venv \
        locales \
        locales-all \
        ffmpeg \
        libsndfile1 \
        netcat-traditional; \
    fi


RUN locale-gen

RUN py -3.11 -m venv myenv \
    && . ./myenv/bin/activate



RUN [ ! -f /usr/lib/python3.11/EXTERNALLY-MANAGED ] || rm -f /usr/lib/python3.11/EXTERNALLY-MANAGED

RUN py -3.11 -m pip install --no-cache-dir -U  --upgrade pip
RUN py -3.11 -m pip install --no-cache-dir -U \
        setuptools \
        wheel

# Copy and install requirements
WORKDIR /app
COPY requirements.txt .
RUN py -3.11 -m pip install --no-cache-dir -r requirements.txt


# Clone and build JamSpell
RUN git clone --recursive https://github.com/bakwc/JamSpell.git /tmp/JamSpell && \
    cd /tmp/JamSpell && \
    mkdir build && cd build && \
    cmake .. && make && \
    cd .. && pip install .

# Install API dependencies
COPY requirements-api.txt .
RUN py -3.11 -m pip install --no-cache-dir -r requirements-api.txt

# Install Wyoming and faster-whisper
RUN py -3.11 -m pip install --no-cache-dir -U --upgrade wyoming faster-whisper

# Runtime stage
FROM ${BASEIMAGE}

# Install runtime dependencies
#RUN apt-get update && \
#    apt-get install -y --no-install-recommends \
#        python3 \
#        python3-pip \
#        ffmpeg \
#        libsndfile1 \
#        netcat-traditional && \
RUN rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
#COPY --from=builder /usr/local/lib/python3.11/dist-packages /usr/local/lib/python3.11/dist-packages
#COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
WORKDIR /app
COPY . .

# Install the package in development mode
RUN py -3.11 -m pip install -e .

# Create directories for models and data
RUN mkdir -p /data/models /data/jamspell

# Copy entrypoint script
WORKDIR /
COPY build/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    HOME=/app \
    PATH="/app/bin:${PATH}"

# Health check and metadata
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:10300/health || exit 1

LABEL org.opencontainers.image.source="https://github.com/cociweb/WhispyWyser"

EXPOSE 10300

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["py", "-3.11", "-m", "whispywyser.cli"]

