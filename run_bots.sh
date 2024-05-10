#!/bin/bash

git pull
git submodule update --init --recursive

docker build -t discord-bots .
if [ "$(uname -s)" == "Linux" ]; then
    # For Linux
    docker run -v "$(pwd)"/models:/app/text-generation-webui/models discord-bots
else
    # For Windows
    docker run -v "/${PWD}/models:/app/text-generation-webui/models" -v "/${PWD}/characters:/app/text-generation-webui/characters" discord-bots
fi
