#!/bin/bash

set -e

cd "$(dirname "$0")"
cd ../../

# Build the image
docker build -t sdk-py-dist-test -f ./tests/distribution/Dockerfile.get_account .

# Run the image
docker run --rm sdk-py-dist-test