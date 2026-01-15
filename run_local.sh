#!/bin/bash
podman run --name leadflow_test \
  --replace \
  --network leadflow-net \
  --dns 8.8.8.8 \
  --env-file .env \
  -p 8000:8000 \
  -d leadflow-local-test
