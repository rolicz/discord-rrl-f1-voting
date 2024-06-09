#!/usr/bin/env python3

import logging
import json
import sys
import argparse
import re
import discord
from datetime import datetime, timedelta
from collections import defaultdict
import asyncio
from PIL import Image, ImageDraw, ImageFont
import os
import atexit
import signal


parser = argparse.ArgumentParser(description='Discord Bot for F1 RRL Voting')
parser.add_argument("-d", "--debug", action=argparse.BooleanOptionalAction)
parser.add_argument("-t", "--token", dest="token", required=True)
parser.add_argument("-g", "--guild-id", dest="guild_id", required=True, type=int)
parser.add_argument("-c", "--channel-id", dest="channel_id", required=True, type=int)
parser.add_argument("-r", "--role-id", dest="role_id", required=True, type=int)
parser.add_argument("-m", "--min-num-racers", dest="min_num_racers", required=True, type=int)
args = parser.parse_args(sys.argv[1:])

if args.debug != None and args.debug is True:
    logging.basicConfig(level=logging.DEBUG)
else:
    logging.basicConfig(level=logging.INFO)


DIRECTORY = 'message_ids_storage'
os.makedirs(DIRECTORY, exist_ok=True)

TOKEN = args.token
MIN_NUM_RACERS = args.min_num_racers
GUILD_ID = args.guild_id
CHANNEL_ID = args.channel_id 
ROLE_ID = args.role_id 
VOTING_CLOSED_HOUR="15:00"

logging.info(f"min racers: {MIN_NUM_RACERS}")
logging.info(f"token     : {TOKEN}")
logging.info(f"guild_id  : {GUILD_ID}")
logging.info(f"channel_id: {CHANNEL_ID}")
logging.info(f"role_id   : {ROLE_ID}")


#EMOJI_TIMESLOTS = {'🕕': '18:00', '🕖': '19:00', '🕗': '20:00'} 
EMOJI_TIMESLOTS = {'6️⃣': '18:00', '7️⃣': '19:00', '8️⃣': '20:00'} 

    
intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.guilds = True  
    
client = discord.Client(intents=intents)
    
# Dictionary to hold message IDs and reaction counts
message_ids = {}

def save_message_ids():
    if message_ids is None or message_ids == {}:
        logging.info(f"msg ids empty")
        return
    current_date = datetime.now().strftime("%Y-%m-%d_%H%M")
    filename = os.path.join(DIRECTORY, f'message_ids_{current_date}.json')
    logging.info(f"store to file {filename}")
    with open(filename, 'w') as file:
        file.write(json.dumps(message_ids, indent=4))

def load_message_ids():
    pattern = re.compile(r'message_ids_(\d{4}-\d{2}-\d{2}_\d{4}).json')
    files = [f for f in os.listdir(DIRECTORY) if pattern.match(f)]
    if not files:
        return {}
    latest_file =""
    try:
        latest_file = max(files, key=lambda f: datetime.strptime(pattern.match(f).group(1), "%Y-%m-%d_%H%M"))

    except Exception as e:
        logging.warning(e)
        return
    logging.info(f"latest file: {latest_file}")
    filepath = os.path.join(DIRECTORY, latest_file)
    if os.path.exists(filepath):
        logging.info(f"load from {filepath}")
        with open(filepath, 'r') as file:
            return json.load(file)

try:
    message_ids = load_message_ids()
    logging.info(f"loaded msg ids: {message_ids}")
except Exception as e:
    pass


def exit_handler():
    logging.info("Saving message_ids before exiting...")
    save_message_ids()

atexit.register(exit_handler)

def signal_handler(signum, frame):
    logging.info(f"Received signal {signum}, saving message_ids...")
    exit_handler()
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)  # Handle Ctrl+C
signal.signal(signal.SIGTERM, signal_handler)  # Handle termination


@client.event
async def on_ready():
    logging.info(f'We have logged in as {client.user}')
    client.loop.create_task(daily_task())
    
@client.event
async def on_message(message):
    logging.info(f"message from {message.author} to {message.channel.id}")
    if message.author == client.user:
        return
    if message.channel.id != CHANNEL_ID:
        return
    
    if message.content.startswith('KW '):
        logging.info(f"received {message.content} from {message.author}")
        try:
            week_number = int(message.content.split()[1])
            await post_weekdays(message.channel, week_number)
        except ValueError:
            await message.channel.send('Invalid week number format. Please use "KW [number]".')
    elif message.content.lower() == 'start':
        await count_reactions_and_generate_charts()
    elif message.content.startswith('debug-store-msg-ids'):
        save_message_ids()
    elif message.content.startswith('debug-load-msg-ids'):
        message_ids = load_message_ids()
        logging.info(f"loaded msg ids: {message_ids}")



@client.event
async def on_connect():
    logging.info('Bot connected')

@client.event
async def on_disconnect():
    logging.warning('Bot disconnected')
    
async def post_weekdays(channel, week_number):
    global message_ids
    message_ids.clear()
    current_year = datetime.now().year
    first_day_of_year = datetime(current_year, 1, 1)
    if first_day_of_year.weekday() > 3:
        first_day_of_year = first_day_of_year + timedelta(7 - first_day_of_year.weekday())
    else:
        first_day_of_year = first_day_of_year - timedelta(first_day_of_year.weekday())
    
    start_date = first_day_of_year + timedelta(weeks=week_number-1)
    weekdays = ['Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag']

    await channel.send(f"<@&{ROLE_ID}>")
    # send info message
    embed = discord.Embed(
        title=f"KW {week_number}",
        description="Bitte reagiert auf die Tage, an denen ihr an einem Rennen teilnehmen könnt.",
        color=discord.Color.blue(),
    )
    embed.add_field(
        name=f":white_check_mark: {VOTING_CLOSED_HOUR} Uhr und {MIN_NUM_RACERS} Teilnehmer",
        value="",
        inline=False,
    )
    embed.add_field(name="Die Zeiten sind wie folgt:", value="", inline=False)
    
    # append the possible time emojis
    for key, value in EMOJI_TIMESLOTS.items():
        embed.add_field(name=f"{key} - {value}\n", value="", inline=False)
    
    await channel.send(embed=embed)



    for i in range(7):
        day_date = start_date + timedelta(days=i)
        day_name = weekdays[day_date.weekday()]
        msg = await channel.send(f'{day_name} {day_date.strftime("%d.%m.")}')
        message_ids[day_name] = msg.id

    
async def daily_task():
    await client.wait_until_ready()
    while not client.is_closed():
        now = datetime.now()
        if now.hour == 15 and now.minute == 0:
            await count_reactions_and_generate_charts()
        await asyncio.sleep(55)
    

async def count_reactions_and_generate_charts():
    channel = client.get_channel(CHANNEL_ID)
    if channel is None:
        print(f"Failed to get channel with ID {CHANNEL_ID}")
        return
    today_name = datetime.now().strftime('%A')
    day_translations = {
        'Monday': 'Montag',
        'Tuesday': 'Dienstag',
        'Wednesday': 'Mittwoch',
        'Thursday': 'Donnerstag',
        'Friday': 'Freitag',
        'Saturday': 'Samstag',
        'Sunday': 'Sonntag'
    }
    today_name_german = day_translations[today_name]
    if today_name_german in message_ids:
        msg_id = message_ids[today_name_german]
        try:
            msg = await channel.fetch_message(msg_id)
        except discord.NotFound:
            print(f"Message ID {msg_id} not found.")
            return

        reaction_counts = defaultdict(lambda: defaultdict(list))
        for reaction in msg.reactions:
            if str(reaction.emoji) in EMOJI_TIMESLOTS:
                async for user in reaction.users():
                    if user != client.user:
                        reaction_counts[today_name_german][EMOJI_TIMESLOTS[str(reaction.emoji)]].append(user.name)

        generate_barchart(today_name_german, reaction_counts)

def generate_barchart(day_name, reaction_counts):
    timeslots = list(EMOJI_TIMESLOTS.values())
    user_counts = {timeslot: len(reaction_counts[day_name][timeslot]) for timeslot in timeslots}
    max_count = max(user_counts.values()) if user_counts else 1

    # Create bar chart image using Pillow
    bar_spacing = 10
    width = len(timeslots * 100) + bar_spacing
    height = max_count * 30 + 100
    bar_width = 90
    block_height = 25 # Height of each user block
    vertical_spacing = 5 

    image = Image.new('RGB', (width, height), (210,210,210))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default()

    for i, timeslot in enumerate(timeslots):
        users = reaction_counts[day_name][timeslot]
        for j, user in enumerate(users):
            bar_height = block_height  # Each block has a fixed height
            x1 = i * (bar_width + bar_spacing) + bar_spacing
            y1 = height - (j + 1) * (block_height + vertical_spacing) - 30
            x2 = x1 + bar_width
            y2 = y1 + block_height
            if len(users) >= MIN_NUM_RACERS:
                draw.rectangle([x1, y1, x2, y2], fill=(0, 153, 0))
            else:
                draw.rectangle([x1, y1, x2, y2], fill=(204, 0, 0))
            draw.text((x1 + 5, y1 + 10), user, fill='white', font=font)

        # Draw the label for the timeslot
        draw.text((i * (bar_width + bar_spacing) + bar_spacing + 5, height - 20), timeslot, fill='black', font=font)

    draw.text((width // 2 - 50, 10), f'Slots für {day_name}', fill='black', font=font)
    image_path = f'{day_name}.png'
    image.save(image_path)

    channel = client.get_channel(CHANNEL_ID)
    if channel is not None:
        asyncio.run_coroutine_threadsafe(channel.send(file=discord.File(f'{day_name}.png')), client.loop)
        os.remove(image_path)
    else:
        print("Failed to send barchart image, channel not found.")


client.run(TOKEN)