#!/bin/bash

git pull
git submodule update --init --recursive

docker build -t discord-bots .
docker run -v "$(pwd)"/models:/app/text-generation-webui/models discord-bots
