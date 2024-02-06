#!/bin/bash

{ echo "N" | bash ./text-generation-webui/start_linux.sh & } | \
  while IFS= read -r line; do
    echo "$line"
    # Stop the text-generation-webui when it has finished launching
    if [[ "$line" == *"Starting Text generation web UI"* ]]; then
      pkill -f "bash ./text-generation-webui/start_linux.sh"
      break
    fi
  done
