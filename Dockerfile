FROM ubuntu:20.04
WORKDIR /app
COPY . .

RUN apt-get update && \
    apt-get install -y python3.8 python3-pip curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
RUN python3.8 -m pip install discord python-dotenv

# Install dos2unix to make ./install_text_generation.sh runnable
RUN apt-get update && apt-get install -y dos2unix
COPY install_text_generation.sh /app/
# Convert line endings to Unix style
RUN dos2unix /app/install_text_generation.sh
# And run the script
RUN bash /app/install_text_generation.sh

CMD ["python3.8", "-u", "./discord_bot.py"]
