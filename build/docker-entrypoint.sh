#!/usr/bin/env bash
python3 -m whispywyser.cli \
    --uri 'tcp://0.0.0.0:10300' \
    --data-dir /data \
    --model-dir /data "$@"
