FROM ubuntu:20.04
WORKDIR /app
COPY . .

RUN apt-get update && \
    apt-get install -y python3.8 python3-pip curl dos2unix && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    python3.8 -m pip install discord python-dotenv

COPY install_text_generation.sh /app/
# Use dos2unix to make ./install_text_generation.sh and ./start_linux.sh runnable (Convert line endings to Unix style)
RUN dos2unix /app/text-generation-webui/start_linux.sh
RUN dos2unix /app/install_text_generation.sh
# And run the script
RUN bash /app/install_text_generation.sh

CMD ["python3.8", "-u", "./discord_bot.py"]
