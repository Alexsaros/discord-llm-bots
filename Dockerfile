FROM ubuntu:20.04
WORKDIR /app
COPY . .

RUN apt-get update && \
    apt-get install -y python3.8 python3-pip curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
RUN python3.8 -m pip install discord python-dotenv

RUN bash ./install_text_generation.sh

CMD ["python3.8", "-u", "./discord_bot.py"]
