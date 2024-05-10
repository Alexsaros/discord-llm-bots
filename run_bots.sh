#!/bin/bash

git pull
git submodule update --init --recursive

# Path to the one_click Python file
python_file="text-generation-webui/one_click.py"
# Check if the file exists
if [ -f "$python_file" ]; then
    # Use sed to comment out the line containing "git pull --autostash" if it hasn't been commented out yet
    # This prevent the text-generation-webui from trying to pull from git
    if ! grep -q "#.*git pull --autostash" "$python_file"; then
        sed -i '/git pull --autostash/s/^/# /' "$python_file"
        echo "Line 271 in $python_file has been commented out."
    fi
else
    echo "Error: $python_file not found."
fi

docker build -t discord-bots .
if [ "$(uname -s)" == "Linux" ]; then
    # For Linux
    docker run -v "$(pwd)"/models:/app/text-generation-webui/models discord-bots
else
    # For Windows
    docker run -v "/${PWD}/models:/app/text-generation-webui/models" -v "/${PWD}/characters:/app/text-generation-webui/characters" discord-bots
fi
