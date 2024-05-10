import os
import subprocess
import discord
import re
import asyncio
import json
import time
import traceback
import aiohttp
from discord.ext import commands, tasks
from dotenv import load_dotenv
from collections import Counter


CMD_FLAGS = "--api --nowebui --model mythomax-l2-13b.ggufv3.q5_1.bin"

headers = {
    "Content-Type": "application/json"
}


async def send_msg_to_llm_stream(character, warm_up=False):
    if character == "RoleplayFacilitator":
        port = 5000
    elif character == "Bob":
        port = 5001
    elif character == "Jahan":
        port = 5002
    else:
        print("INVALID CHARACTER %s GIVEN!" % character)
        return
    stream_url = "http://127.0.0.1:%s/v1/chat/completions" % port

    STOPPING_STRINGS = ['Melissa:', 'Bairdotr:', 'Jahan:', 'Bob:', 'User:', 'You:', "Alexsaro:", "BlueberryCookie:"]
    if character == "RoleplayFacilitator":
        # STOPPING_STRINGS.remove("Bob:")
        # STOPPING_STRINGS.remove("Jahan:")
        STOPPING_STRINGS = []
    if character + ":" in STOPPING_STRINGS:
        STOPPING_STRINGS.remove(character + ":")

    # Parse the message history into the correct format for the bot
    chat_history = []
    message_entry = {"role": "", "content": ""}
    for message in global_history:
        message_entry = {"role": "user", "content": ""}
        # Check if this message is a response from this character
        if message.author == character:
            message_entry["role"] = "assistant"
            message_entry["content"] = message.text
            chat_history.append(message_entry)
        else:
            message_entry["content"] = message.formatted_msg
            chat_history.append(message_entry)

    if character == "RoleplayFacilitator":
        character_selection_msg = """If anyone, who should respond to this conversation? Mention only the person who should respond, and nothing else. Someone should only respond if they are being addressed, mentioned, responded to, or have something to contribute to the conversation.
        - Bob
        - Jahan
        - No one
        - Someone else (e.g. Alexsaro, Blueberrycookie, Bairdotr, Melissa)
        Which of the listed options should respond? Be concise. The one who should respond is:"""
        # Taking into account each character's personality and the above conversation, the one who should respond is:"""
        message_entry = {"role": "user", "content": character_selection_msg}
        chat_history.append(message_entry)

    if warm_up:
        message_entry = {"role": "user", "content": 'Reply only with the word "yes".'}
        chat_history = [message_entry]
    if character != "RoleplayFacilitator":
        print("--- History: ---")
        print(chat_history)
        print("Relevant message: " + str(message_entry))
    
    data = {
        "mode": "chat",
        "character": character,
        "stream": True,
        "messages": chat_history
    }

    response = ""
    while not response:
        async with aiohttp.ClientSession() as session:
            async with session.post(stream_url, headers=headers, json=data, timeout=None) as sess_response:
                async for chunk, _ in sess_response.content.iter_chunks():
                    chunk = chunk.decode('utf-8')
                    if chunk.startswith("data: "):
                        chunk = chunk[6:]
                    chunk = chunk.strip()
                    if not chunk:
                        continue
                    if chunk[:4] == "ping" or chunk[:6] == ": ping":
                        print(chunk)
                        continue
                    payload = json.loads(chunk)
                    response += payload['choices'][0]['message']['content']

                    if character == "RoleplayFacilitator" and len(response) >= 10:
                        yield response
                        return

                    # Make sure the bot does not start talking as another user/character
                    for stopping_string in STOPPING_STRINGS:
                        if stopping_string in response:
                            print("Stopped stopping_string '%s' from being printed in: '%s' (%s)" % (stopping_string, response, stopping_string in response))
                            response = response.split(stopping_string)[0]
                            response = response.strip('\n')
                            print("new response: '%s'" % response)
                            yield response
                            return
                    yield response

        if not response:
            await asyncio.sleep(0.5)


class Message:

    def __init__(self, message_object):
        if not message_object:
            raise Exception("No message object passed to init of Message.")
        self.update_self(message_object)
    
    def update_self(self, message_object):
        self.object = message_object
        # Uses the saved Discord message object to update this object's attributes
        self.text = self.object.content
        self.author = self.object.author.global_name if self.object.author.global_name else self.object.author.name
        self.formatted_msg = self.author + ": " + self.text
        self.id = self.object.id
        
    def __str__(self):
        return str(self.id) + ": " + self.formatted_msg



current_message_being_send = None
current_response = ""
last_message_sent_time_per_channel = {}

# Stores all the messages so far (that are relevant to the bot) as Message objects
global_history = []
new_messages = []

bot_busy = True
bot_jahan_busy = True

# Keeps track of how many times the bot did not respond in a row
did_not_respond_count = 0
SLEEP_AFTER_X_NO_RESPONSES = 2

messages_to_handle = []

load_dotenv()
TOKEN_BOB = os.getenv('DISCORD_TOKEN_BOB')
TOKEN_JAHAN = os.getenv('DISCORD_TOKEN_JAHAN')

intents = discord.Intents.default()
intents.message_content = True

bot_bob = commands.Bot(command_prefix='!', intents=intents)
bot_jahan = commands.Bot(command_prefix='!', intents=intents)

BOT_ID_BOB = 1143932283997401089
BOT_ID_JAHAN = 1181674509749719040

heartbeat_started = False


async def start_llm(port, facilitator=False):
    if facilitator:
        command = 'bash ./text-generation-webui/start_linux.sh --api-port %s --settings ../settings_facilitator.yaml %s' % (port, CMD_FLAGS)
    else:
        command = 'bash ./text-generation-webui/start_linux.sh --api-port %s --settings ../settings.yaml %s' % (port, CMD_FLAGS)
    process = subprocess.Popen([command], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)

    url = "http://127.0.0.1:%s" % port
    # Monitor the output until the server has started
    while True:
        # Read a line from the stdout
        line = process.stdout.readline()

        # Return if there's no more output and the process has finished
        if not line and process.poll() is not None:
            print("Starting server has finished, but did not detect an IP!")
            return

        # Decode the line from bytes to string
        line = line.decode('utf-8').strip()
        print(line)

        # Check if the URL has been printed
        if url in line:
            return


async def who_should_respond():
    characters = {"some": "No one", "no": "No one", "alex": "No one", "blueberrycookie": "No one", "bairdotr": "No one", "melissa": "No one",
                  "bob": "Bob", "jahan": "Jahan"}
    chosen_characters = []

    # Try X times
    for i in range(4):
        char_response = ""
        try:
            async for response in send_msg_to_llm_stream("RoleplayFacilitator"):
                char_response = response
        except Exception as e:
            print("Failed determining who should respond: %s" % e)
            print("Starting RoleplayFacilitator's LLM...")
            port = 5000
            subprocess.Popen(['bash ./text-generation-webui/start_linux.sh --api-port %s --settings ../settings_facilitator.yaml %s' % (port, CMD_FLAGS)],
                             stdin=subprocess.PIPE, shell=True)
            await asyncio.sleep(10)
            continue
        char_response = char_response.lower().strip(" :;\"'-.,()_!?\n\t")
        if char_response.startswith("only "):
            char_response = char_response[5:].strip()
        print("chosen char: '%s'" % char_response)
        await asyncio.sleep(1)    # Give the LLM some time to recover

        # Find the character that has been chosen
        for char in characters.keys():
            if char_response.startswith(char):
                chosen_characters.append(characters[char])
                break

        print(chosen_characters)
        # If a character has been chosen two times, return it
        if len(chosen_characters) > 1:
            char_count = Counter(chosen_characters)
            most_common_char = char_count.most_common(1)[0]
            if most_common_char[1] >= 2:
                return most_common_char[0]

    # Unable to quickly determine who should respond, so probably not important
    print("Could not determine who should respond.\n")
    return "No one"


# BOT BOB CODE

@bot_bob.event
async def on_ready():
    global bot_busy, heartbeat_started
    print(f'{bot_bob.user} has connected to Discord!')
    if not heartbeat_started:
        heartbeat.start()  # Start the background task
    heartbeat_started = True
    handle_incoming_messages.start()
    # Wait until Jahan has been fully set up
    # while bot_jahan_busy:
    #     await asyncio.sleep(1)

    print("Starting RoleplayFacilitator's LLM...")
    port = 5000
    await start_llm(port, facilitator=True)

    print("\nWarming up RoleplayFacilitator's LLM...")
    character = "RoleplayFacilitator"
    async for response in send_msg_to_llm_stream(character, warm_up=True):
        warmed_up_response = response
    print(character + ": " + warmed_up_response + "\n")

    print("Starting Bob's LLM...")
    port = 5001
    await start_llm(port)

    print("\nWarming up Bob's LLM...")
    character = "Bob"
    async for response in send_msg_to_llm_stream(character, warm_up=True):
        warmed_up_response = response
    print(character + ": " + warmed_up_response + "\n")

    bot_busy = False


def process_message(message, preceding_msg):
    global new_messages, last_message_sent_time_per_channel
    if preceding_msg:
        # Add the preceding message, if it is not already the last message sent
        last_msg = None
        if new_messages:
            last_msg = new_messages[-1]
        elif global_history:
            last_msg = global_history[-1]
        if not last_msg or last_msg.id != preceding_msg.id:
            new_messages.append(Message(preceding_msg))
    # Add the newly received message
    new_messages.append(Message(message))
    # Reset the timeout for the bot to become inactive in this channel
    last_message_sent_time_per_channel[message.channel.id] = time.time()

async def send_new_response():
    global bot_busy, current_response, current_message_being_send, new_messages, global_history, did_not_respond_count
    bot_busy = True

    # Add the newly received messages to the history
    global_history += new_messages
    new_messages = []

    selected_bot = None
    character = await who_should_respond()
    if character not in ["No one", "Bob", "Jahan"]:
        print("INVALID CHARACTER CHOSEN: %s" % character)
        return

    if character == "Bob":
        selected_bot = bot_bob
    elif character == "Jahan":
        selected_bot = bot_jahan

    # Prevent the bot from sending more than one message in a row
    last_message = None     # type: Message
    if global_history:
        last_message = global_history[-1]
    if selected_bot and last_message:
        if selected_bot.user.id == last_message.object.author.id:
            print("Preventing %s from responding to themselves." % character)
            character = "No one"

    if character == "No one":
        print("No one should respond.")
        did_not_respond_count += 1
        # Bot is probably not relevant to the conversation anymore, so let them sleep until awoken again
        if did_not_respond_count >= SLEEP_AFTER_X_NO_RESPONSES:
            print("Did not respond %s times. Going to sleep..." % did_not_respond_count)
            last_message_sent_time_per_channel = {}
            did_not_respond_count = 0
        bot_busy = False
        return
    did_not_respond_count = 0

    if new_messages:
        last_msg = new_messages[-1]
    else:
        last_msg = global_history[-1]
    # Get the channel from the correct bot's POV
    channel_obj = selected_bot.get_channel(last_msg.object.channel.id)
    # Send a message that will later be edited live with the bot's response
    current_message_being_send = await channel_obj.send("*Thinking...*")
    # Add the newly received messages to the history at the moment the "Thinking" response had been sent
    global_history += new_messages
    new_messages = []

    # Simulate typing
    async with channel_obj.typing():
        try:
            async for response in send_msg_to_llm_stream(character):
                current_response = response
        except Exception as e:
            print(str(e))
    print(character + ": " + current_response + "\n")

    bot_busy = False


@tasks.loop(seconds=0.1)
async def handle_incoming_messages():
    global last_message_sent_time_per_channel, global_history, new_messages, messages_to_handle
    if not messages_to_handle:
        return
    try:
        # Make sure the messages are being parsed in the order they come in
        message = messages_to_handle[0]

        # Skip messages sent by one of the bots
        if message.author == bot_bob.user or message.author == bot_jahan.user:
            return

        ctx = await bot_bob.get_context(message)
        if message.content.lower() == "be quiet":
            print("Bots will now be quiet.")
            last_message_sent_time_per_channel = {}
            new_messages = []
            return

        if message.content.lower() == "reset":
            print("Resetting all bot variables.")
            last_message_sent_time_per_channel = {}
            new_messages = []
            global_history = []
            return

        sender = message.author.global_name if message.author.global_name else message.author.name
        print("%s: %s" % (sender, message.content))

        # Finds any preceding/relevant earlier message to give the bot more context
        preceding_message = None
        earlier_messages = [msg async for msg in message.channel.history(limit=5)]
        reached_current_message = False
        for i, old_message in enumerate(earlier_messages):
            if reached_current_message:
                if old_message.author != bot_bob.user:
                    preceding_message = old_message
                break
            if message.id == old_message.id:
                reached_current_message = True
        # If this message is a response, include the original message
        if message.reference:
            preceding_message = await ctx.fetch_message(message.reference.message_id)
            # If the message referenced is the last message received, don't include it to prevent duplicates
            if new_messages:
                if new_messages[-1].id == preceding_message.id:
                    preceding_message = None
            elif global_history:
                if global_history[-1].id == preceding_message.id:
                    preceding_message = None

        words = re.findall(r"[\w']+|[.,!?;]", message.content)
        words = [word.lower() for word in words]

        # Respond to messages sent within an hour after the bot's last message in that channel
        channel_id = message.channel.id
        if channel_id in last_message_sent_time_per_channel:
            if time.time() - last_message_sent_time_per_channel[channel_id] < 3600:
                process_message(message, preceding_message)
                return

        # Respond to messages mentioning Bob or Jahan
        if "bob" in words or "jahan" in words:
            process_message(message, preceding_message)
            return

        # Respond to messages referencing the bot's message
        if message.reference:
            original_msg = await ctx.fetch_message(message.reference.message_id)
            if original_msg.author.id == BOT_ID_BOB or original_msg.author.id == BOT_ID_JAHAN:
                process_message(message, preceding_message)
                return

    except Exception as e:
        print("Encountered exception: %s" % e)
        print(traceback.format_exc(e))
    finally:
        messages_to_handle.remove(message)


@tasks.loop(seconds=1)
async def heartbeat():
    global current_message_being_send, current_response, new_messages
    # Update the sent message with the newly generated words
    if current_message_being_send and current_response:
        await current_message_being_send.edit(content=current_response)
    # If a message is still busy being generated, do nothing
    if bot_busy:
        return
    # The message has fully generated and has been sent, so save it and reset the message variables
    if current_message_being_send:
        # Make sure the message actually contains the final response
        await current_message_being_send.edit(content=current_response)
        # Add the final message object to the message history
        ctx = await bot_bob.get_context(current_message_being_send)
        final_message = await ctx.fetch_message(current_message_being_send.id)
        # Add it to the start of new messages so the bot could respond to it again, even if no new messages occurred
        new_messages.insert(0, Message(final_message))
        # Reset the variables
        current_response = ""
        current_message_being_send = None
    # No new message to respond to, so do nothing
    if not new_messages:
        return
    # Received new message to respond to
    # TODO fix tasks carried out when previous response went to sleep
    asyncio.create_task(send_new_response())


@bot_bob.event
async def on_error(event, *args, **kwargs):
    print('Encountered error')
    with open('err.log', 'a') as f:
        if event == 'on_message':
            f.write(f'Unhandled message: {args[0]}\n')
        else:
            raise


@bot_bob.event
async def on_message(message):
    global last_message_sent_time_per_channel, global_history, new_messages, messages_to_handle
    messages_to_handle.append(message)


# BOT JAHAN CODE

@bot_jahan.event
async def on_ready():
    global bot_jahan_busy
    print(f'{bot_jahan.user} has connected to Discord!')
    print("Starting Jahan's LLM...")
    port = 5002
    await start_llm(port)
    print("\nWarming up Jahan's LLM...")
    character = "Jahan"
    async for response in send_msg_to_llm_stream(character, warm_up=True):
        warmed_up_response = response
    print(character + ": " + warmed_up_response + "\n")
    bot_jahan_busy = False


loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
loop.create_task(bot_bob.start(TOKEN_BOB))
loop.create_task(bot_jahan.start(TOKEN_JAHAN))
loop.run_forever()
