import os
import subprocess
import discord
import re
import asyncio
import json
import requests_async as requests
import websockets
import html
import time
from discord.ext import commands, tasks
from dotenv import load_dotenv

# For local streaming, the websockets are hosted without ssl - http://
HOST = 'localhost:5000'
URI = f'http://{HOST}/api/v1/chat'


async def send_msg_to_llm(user_input, history):
    STOPPING_STRINGS = ['Melissa:', 'Bairdotr:', 'Jahan:', 'User:', 'You:', "Alexsaro:", "BlueberryCookie:"]
    
    request = {
        'user_input': user_input,
        'max_new_tokens': 300,
        'auto_max_new_tokens': False,
        'history': history,
        'mode': 'chat',  # Valid options: 'chat', 'chat-instruct', 'instruct'
        'character': 'Bob',
        'instruction_template': 'test_template',  # Will get autodetected if unset
        'your_name': 'User',
        # 'name1': 'name of user', # Optional
        # 'name2': 'name of character', # Optional
        # 'context': 'character context', # Optional
        # 'greeting': 'greeting', # Optional
        # 'name1_instruct': 'You', # Optional
        # 'name2_instruct': 'Assistant', # Optional
        # 'context_instruct': 'context_instruct', # Optional
        # 'turn_template': 'turn_template', # Optional
        'regenerate': False,
        '_continue': False,
        'chat_instruct_command': 'Continue the chat dialogue below. Write a single reply for the character "<|character|>".\n\n<|prompt|>',

        # Generation params. If 'preset' is set to different than 'None', the values
        # in presets/preset-name.yaml are used instead of the individual numbers.
        'preset': 'Shortwave',
        'do_sample': True,
        'temperature': 0.7,
        'top_p': 0.1,
        'typical_p': 1,
        'epsilon_cutoff': 0,  # In units of 1e-4
        'eta_cutoff': 0,  # In units of 1e-4
        'tfs': 1,
        'top_a': 0,
        'repetition_penalty': 1.18,
        'repetition_penalty_range': 0,
        'top_k': 40,
        'min_length': 0,
        'no_repeat_ngram_size': 0,
        'num_beams': 1,
        'penalty_alpha': 0,
        'length_penalty': 1,
        'early_stopping': False,
        'mirostat_mode': 0,
        'mirostat_tau': 5,
        'mirostat_eta': 0.1,
        'guidance_scale': 1,
        'negative_prompt': '',

        'seed': -1,
        'add_bos_token': True,
        'truncation_length': 2048,
        'ban_eos_token': False,
        'skip_special_tokens': True,
        'stopping_strings': STOPPING_STRINGS
    }

    response = await requests.post(URI, json=request)

    if response.status_code == 200:
        result = response.json()['results'][0]['history']
        # print(json.dumps(result, indent=4))
        response = html.unescape(result['visible'][-1][1])
        for stopping_string in STOPPING_STRINGS:
            split_response = response.split(stopping_string)
            response = split_response[0].strip('\n')
        return response

class LlmRequest:

    def __init__(self, message_object=None, message_str=None, preceding_message=None):
        self.msg_obj = message_object    # Discord Message object
        self.message = ""
        if self.msg_obj:
            sender = self.msg_obj.author.global_name
            self.message = sender + ": " + self.msg_obj.content
        if message_str:
            self.message = message_str
        self.send_response = True if self.msg_obj else False
        # Add the preceding message before the current message string
        if preceding_message:
            sender = preceding_message.author.global_name if preceding_message.author.global_name else preceding_message.author.name
            preceding_message_str = sender + ": " + preceding_message.content
            self.message = preceding_message_str + "\n" + self.message

queue = None
llm_task = None
current_llm_request = None
chat_history = {'internal': [], 'visible': []}
last_message_sent_time_per_channel = {}

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
bot = commands.Bot(command_prefix='!', intents=intents)

BOT_ID = 1143932283997401089

@bot.event
async def on_ready():
    global queue
    queue = asyncio.Queue()
    print(f'{bot.user} has connected to Discord!')
    print('Starting the LLM...')
    script = subprocess.Popen(['./start_linux.sh'], stdin=subprocess.PIPE, shell=True)
    llm_queue_checker.start()  # Start the background task
    await asyncio.sleep(30)
    print("\nWarming up the LLM...")
    await queue.put(LlmRequest(message_str='Reply only with the word "yes".'))

async def process_llm_request(llm_request):
    global chat_history, last_message_sent_time_per_channel
    print("Starting LLM request.")
    request_msg = llm_request.message

    if llm_request.msg_obj is None:
        response = await send_msg_to_llm(request_msg, chat_history)
    else:
        # Simulate typing
        async with llm_request.msg_obj.channel.typing():
            response = await send_msg_to_llm(request_msg, chat_history)

    if llm_request.send_response:
        message_response_pair = [request_msg, response]
        # Save the new messages in the chat history, so the bot remembers it
        chat_history["internal"].append(message_response_pair)
        chat_history["visible"].append(message_response_pair)
        print("Bob: " + response + "\n")
        await llm_request.msg_obj.reply(response)
        channel_id = llm_request.msg_obj.channel.id
        last_message_sent_time_per_channel[channel_id] = time.time()
    queue.task_done()

@tasks.loop(seconds=0.5)
async def llm_queue_checker():
    global queue, llm_task, current_llm_request
    if llm_task and not llm_task.done():
        return
    if queue is None or queue.empty():
        return
    current_llm_request = await queue.get()
    llm_task = asyncio.create_task(process_llm_request(current_llm_request))


@bot.event
async def on_error(event, *args, **kwargs):
    print('Encountered error')
    with open('err.log', 'a') as f:
        if event == 'on_message':
            f.write(f'Unhandled message: {args[0]}\n')
        else:
            raise

@bot.event
async def on_message(message):
    global queue, last_message_sent_time_per_channel, chat_history
    try:
        # Skip messages sent by this bot
        if message.author == bot.user:
            return

        ctx = await bot.get_context(message)

        if message.content.lower() == "be quiet":
            last_message_sent_time_per_channel = {}
            return

        if message.content.lower() == "reset":
            last_message_sent_time_per_channel = {}
            chat_history = {'internal': [], 'visible': []}
            return

        sender = message.author.global_name
        print(sender + ": " + message.content)

        # Finds any preceding/relevant earlier message to give the bot more context
        preceding_message = None
        earlier_messages = [msg async for msg in message.channel.history(limit=5)]
        reached_current_message = False
        for i, old_message in enumerate(earlier_messages):
            if reached_current_message:
                if old_message.author != bot.user:
                    preceding_message = old_message
                break
            if message.id == old_message.id:
                reached_current_message = True
        # If this message is a response, include the original message
        if message.reference:
            preceding_message = await ctx.fetch_message(message.reference.message_id)
            try:
                # If the message referenced is the last response, don't include it to prevent duplicates
                if chat_history['visible'][-1][1] == preceding_message.content:
                    preceding_message = ""
            except IndexError:
                pass

        words = re.findall(r"[\w']+|[.,!?;]", message.content)
        words = [word.lower() for word in words]

        # Respond to messages sent within an hour after the bot's last message in that channel
        channel_id = message.channel.id
        if channel_id in last_message_sent_time_per_channel:
            if time.time() - last_message_sent_time_per_channel[channel_id] < 3600:
                await queue.put(LlmRequest(message_object=message, preceding_message=preceding_message))
                return

        # Respond to messages referencing the bot's message
        if message.reference:
            original_msg = await ctx.fetch_message(message.reference.message_id)
            if original_msg.author.id == BOT_ID:
                await queue.put(LlmRequest(message_object=message, preceding_message=preceding_message))
                return

        # Respond to messages mentioning Bob
        if "bob" in words:
            await queue.put(LlmRequest(message_object=message, preceding_message=preceding_message))
            return

    except Exception as e:
        print("Encountered exception: %s" % e)

bot.run(TOKEN)
