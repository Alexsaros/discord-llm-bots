#!/bin/bash

git pull
git submodule update --init --recursive

docker build -t discord-bots .
if [ "$(expr substr $(uname -s) 1 5)" == "Linux" ]; then
    # For Linux
    docker run -v "$(pwd)"/models:/app/text-generation-webui/models discord-bots
else
    # For Windows
    docker run -v "%cd%/models:/app/text-generation-webui/models" discord-bots
fi
