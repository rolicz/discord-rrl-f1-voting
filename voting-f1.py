#!/usr/bin/env python3

import logging
import json
import sys
import argparse
import re
import discord
from discord.ext import tasks
from datetime import datetime, timedelta, time
from collections import defaultdict
import asyncio
from PIL import Image, ImageDraw, ImageFont
import os
import atexit
import signal
import zoneinfo

RACERS = {
    "jisifus"           : "Arthur",
    "pjgangster"        : "Peter",
    "nynedine"          : "Kili",
    "shevve"            : "Steve",
    "metschamonoqueem"  : "Simon",
    "jani0166"          : "Jan",
    "vsares"            : "Massl",
    "thedohn"           : "Edon",
    "flocz"             : "Flo",
    "rolicz"            : "Roli",
    "eisidrive"         : "Eisi",
    "lukas6662"         : "Ropi",
    #"kleschmabilla"     : "Franzi",
    "msebastian"        : "Sebastian",
    "kaizerkarl"        : "Karli",
}

DAY_TRANSLATIONS = {
    'Monday'   : 'Montag',
    'Tuesday'  : 'Dienstag',
    'Wednesday': 'Mittwoch',
    'Thursday' : 'Donnerstag',
    'Friday'   : 'Freitag',
    'Saturday' : 'Samstag',
    'Sunday'   : 'Sonntag'
}

parser = argparse.ArgumentParser(description='Discord Bot for F1 RRL Voting')
parser.add_argument("-d", "--debug", action=argparse.BooleanOptionalAction)
parser.add_argument("-t", "--token", dest="token", required=True)
parser.add_argument("-g", "--guild-id", dest="guild_id", required=True, type=int)
parser.add_argument("-c", "--channel-id", dest="channel_id", required=True, type=int)
parser.add_argument("-r", "--role-id", dest="role_id", required=True, type=int)
parser.add_argument("-m", "--min-num-racers", dest="min_num_racers", required=True, type=int)
args = parser.parse_args(sys.argv[1:])

class LoggerGen:
    @staticmethod
    def gen_logger(debug=False):
        logger = logging.getLogger()
        file_handler = logging.FileHandler(filename='./output.log', mode='w')
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%m/%d/%Y %H:%M:%S %p')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        if debug:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.INFO)
        return logger
    
debug = False
if args.debug is not None and args.debug is True:
    debug = True
logger = LoggerGen.gen_logger(debug)


DIRECTORY = 'message_ids_storage'
os.makedirs(DIRECTORY, exist_ok=True)

TOKEN = args.token
MIN_NUM_RACERS = args.min_num_racers
GUILD_ID = args.guild_id
CHANNEL_ID = args.channel_id 
ROLE_ID = args.role_id

logging.info(f"min racers     : {MIN_NUM_RACERS}")
# logging.info(f"token          : {TOKEN}")
logging.info(f"guild_id       : {GUILD_ID}")
logging.info(f"channel_id     : {CHANNEL_ID}")
logging.info(f"role_id        : {ROLE_ID}")


EMOJI_TIMESLOTS = {'6️⃣': '18:00', '7️⃣': '19:00', '8️⃣': '20:00', '🌃': '20:30'}
EMOJI_NOT_AVAILABLE = ['👎']
logging.info(f"EMOJI_TIMESLOTS: {EMOJI_TIMESLOTS}")

TIMEZONE = zoneinfo.ZoneInfo("Europe/Vienna")
VOTING_CLOSED_HOUR = 15
VOTING_UPDATE_DAY = 6  # Sunday

VOTING_UPDATE_TIME = time(22, 0, tzinfo=TIMEZONE)
VOTING_REMINDER_TIME = time(VOTING_CLOSED_HOUR - 1, 0, tzinfo=TIMEZONE)
VOTING_EVALUATION_TIME = time(VOTING_CLOSED_HOUR, 0, tzinfo=TIMEZONE)

VOTING_REMINDER_IMAGE_PATH = 'assets/voting_reminder.png'

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.guilds = True
intents.members = True
    
client = discord.Client(intents=intents)

# Dictionary to hold message IDs and reaction counts
message_ids = {}
prev_chart_id = None

def save_message_ids():
    if message_ids is None or message_ids == {}:
        logging.info(f"msg ids empty")
        return
    current_date = datetime.now().strftime("%Y-%m-%d_%H%M")
    filename = os.path.join(DIRECTORY, f'message_ids_{current_date}.json')
    logging.info(f"store message ids to file {filename}")
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
    logging.debug(f"latest file: {latest_file}")
    filepath = os.path.join(DIRECTORY, latest_file)
    if os.path.exists(filepath):
        logging.info(f"load from {filepath}")
        with open(filepath, 'r') as file:
            return json.load(file)
    
def save_prev_chart_id():
    if prev_chart_id is None:
        logging.info(f"prev_chart_id is None: nothing saved")
        return
    current_date = datetime.now().strftime("%Y-%m-%d_%H%M")
    filename = os.path.join(DIRECTORY, f'prev_chart_id_{current_date}.json')
    logging.info(f"store previous chart ids to file {filename}")
    with open(filename, 'w') as file:
        file.write(json.dumps(prev_chart_id, indent=4))

def load_prev_chart_id():
    pattern = re.compile(r'prev_chart_id_(\d{4}-\d{2}-\d{2}_\d{4}).json')
    files = [f for f in os.listdir(DIRECTORY) if pattern.match(f)]
    if not files:
        return None
    latest_file =""
    try:
        latest_file = max(files, key=lambda f: datetime.strptime(pattern.match(f).group(1), "%Y-%m-%d_%H%M"))
    except Exception as e:
        logging.warning(e)
        return None
    logging.debug(f"latest file: {latest_file}")
    filepath = os.path.join(DIRECTORY, latest_file)
    if os.path.exists(filepath):
        logging.info(f"load from {filepath}")
        with open(filepath, 'r') as file:
            return json.load(file)

try:
    message_ids = load_message_ids()
    logging.info(f"loaded msg ids: {message_ids}")
    prev_chart_id = load_prev_chart_id()
    logging.info(f"loaded prev_chart_id: {prev_chart_id}")
except Exception as e:
    pass


def exit_handler():
    logging.info("Saving message_ids before exiting...")
    save_message_ids()
    save_prev_chart_id()

atexit.register(exit_handler)

def signal_handler(signum, frame):
    logging.info(f"Received signal {signum}, saving message_ids...")
    exit_handler()
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)  # Handle Ctrl+C
signal.signal(signal.SIGTERM, signal_handler)  # Handle termination


@tasks.loop(time=VOTING_UPDATE_TIME)
async def weekly_new_voting_task():
    now = datetime.now()

    if now.weekday() != VOTING_UPDATE_DAY:
        next_update = (VOTING_UPDATE_DAY - now.weekday()) % 7
        logging.info(f"Skipping weekly voting update, next update in {next_update} days.")
        return

    monday = now + timedelta(days=1)
    week_number = monday.isocalendar().week

    channel = client.get_channel(CHANNEL_ID)
    if channel is not None:
        logging.info(f"post new voting at {now.isoformat()}")
        await post_new_voting(channel, week_number)
    else:
        logging.warning("Failed to post new voting, channel not found.")


@tasks.loop(time=VOTING_REMINDER_TIME)
async def daily_voting_reminder_task():
    await send_private_message_voting_reminder()


@tasks.loop(time=VOTING_EVALUATION_TIME)
async def daily_voting_evaluation_task():
    await delete_previous_chart()
    await count_reactions_and_generate_charts()


@client.event
async def on_ready():
    logging.info(f'We have logged in as {client.user}')

    # start all the scheduled tasks
    logging.info(f"Starting voting poll task. Runs everyday at {VOTING_UPDATE_TIME}")
    weekly_new_voting_task.start()
    logging.info(f"Starting voting reminder task. Runs everyday at {VOTING_REMINDER_TIME}")
    daily_voting_reminder_task.start()
    logging.info(f"Starting voting evaluation task. Runs everyday at {VOTING_EVALUATION_TIME}")
    daily_voting_evaluation_task.start()
    # today_name_german = get_day_of_week()
    # reaction_counts, not_available_users, available_users = await count_reactions_for_day(today_name_german)
    # logging.info(f"reactions: {reaction_counts}")
    # logging.info(f"not available: {not_available_users}")
    # logging.info(f"available: {available_users}")


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
            await post_new_voting(message.channel, week_number)
            save_message_ids()
        except ValueError:
            await message.channel.send('Invalid week number format. Please use "KW [number]".')
    elif message.content.lower() == 'start':
        await delete_previous_chart()
        await count_reactions_and_generate_charts()
    elif message.content.lower() == 'send-reminder':
        await send_private_message_voting_reminder()
    elif message.content.startswith('debug-store-msg-ids'):
        save_message_ids()
        save_prev_chart_id()
    elif message.content.startswith('debug-load-msg-ids'):
        message_ids = load_message_ids()
        logging.info(f"loaded msg ids: {message_ids}")
        prev_chart_id = load_prev_chart_id()
        logging.info(f"loaded prev_chart_id: {prev_chart_id}")


@client.event
async def on_connect():
    logging.info('Bot connected')


@client.event
async def on_disconnect():
    logging.warning('Bot disconnected')


async def post_new_voting(channel, week_number):
    now = datetime.now()
    global message_ids
    message_ids.clear()
    current_year = now.year
    first_day_of_year = datetime(current_year, 1, 1)
    logging.info(f"Create new voting for week {week_number} at {now}, year {current_year}, first day of the year: {first_day_of_year}")
    if first_day_of_year.weekday() > 3:
        first_day_of_year = first_day_of_year + timedelta(7 - first_day_of_year.weekday())
    else:
        first_day_of_year = first_day_of_year - timedelta(first_day_of_year.weekday())
    
    start_date = first_day_of_year + timedelta(weeks=week_number-1)
    weekdays = list(DAY_TRANSLATIONS.values())

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
    

async def count_reactions_for_day(today_name_german):
    channel = client.get_channel(CHANNEL_ID)
    if channel is None:
        logging.warning(f"Failed to get channel with ID {CHANNEL_ID}")
        return None, None, None

    if today_name_german not in message_ids:
        logging.warning(f"Message ID for {today_name_german} not found.")
        return None, None, None

    msg_id = message_ids[today_name_german]
    try:
        msg = await channel.fetch_message(msg_id)
    except discord.NotFound:
        logging.warning(f"Message ID {msg_id} not found.")
        return None, None, None

    reaction_counts = defaultdict(lambda: defaultdict(list))
    not_available_users = set()
    available_users = set()
    for reaction in msg.reactions:
        if str(reaction.emoji) in EMOJI_TIMESLOTS:
            async for user in reaction.users():
                if user != client.user:
                    reaction_counts[today_name_german][EMOJI_TIMESLOTS[str(reaction.emoji)]].append(user.name)
                    available_users.add(user.name)
        if str(reaction.emoji) in EMOJI_NOT_AVAILABLE:
            async for user in reaction.users():
                if user != client.user:
                    not_available_users.add(user.name)

    return reaction_counts, not_available_users, available_users


def get_not_voted_users(not_available_users, available_users):
    channel = client.get_channel(CHANNEL_ID)
    if channel is None:
        logging.warning(f"Failed to get channel with ID {CHANNEL_ID}")
        return []

    # Get all users who have not voted yet
    all_users = set(RACERS.keys())
    voted_users = not_available_users.union(available_users)
    not_voted_users = all_users.difference(voted_users)

    users_to_dm = []
    for member in channel.members:
        if member.name in not_voted_users:
            users_to_dm.append(member)

    return users_to_dm


def get_day_of_week():
    today_name = datetime.now().strftime('%A')
    return DAY_TRANSLATIONS[today_name]


async def send_private_message_voting_reminder():
    logging.info("Sending voting reminder...")
    today_name_german = get_day_of_week()
    reaction_counts, not_available_users, available_users = await count_reactions_for_day(today_name_german)
    if reaction_counts is None or not_available_users is None or available_users is None:
        logging.warning("Failed to count reactions for today.")
        return

    users = get_not_voted_users(not_available_users, available_users)

    for user in users:
        try:
            logging.info(f"Sending vote reminder to {user.name}")
            await user.send(f"Bro scherts dich abstimmen?")
            await user.send(file=discord.File(VOTING_REMINDER_IMAGE_PATH))
        except Exception as e:
            logging.warning(f"Could not send vote reminder to {user.name}")


async def delete_previous_chart():
    global prev_chart_id
    channel = client.get_channel(CHANNEL_ID)
    if channel is not None:
        if prev_chart_id is not None:
            try:
                prev_chart_message = await channel.fetch_message(prev_chart_id)
                logging.info(f"delete previous chart {prev_chart_id}")
                await prev_chart_message.delete()
                prev_chart_id = None
            except Exception as e:
                logging.warning(f"could not delete previous chart {prev_chart_id} ({e})")

async def count_reactions_and_generate_charts():
    logging.info("Counting reactions and generating charts...")
    today_name_german = get_day_of_week()
    reaction_counts, not_available_users, available_users = await count_reactions_for_day(today_name_german)
    if reaction_counts is None or not_available_users is None or available_users is None:
        logging.warning("Failed to count reactions for today.")
        return

    await generate_barchart(today_name_german, reaction_counts, not_available_users, available_users)


def getUserRealName(user):
    if user in RACERS:
        return RACERS[user]
    else:
        return user


async def generate_barchart(day_name, reaction_counts, not_available_users, available_users):
    global prev_chart_id
    logging.info(f"generate chart for {day_name}")
    logging.info(f"available: {available_users}")
    logging.info(f"not available: {not_available_users}")
    timeslots = list(EMOJI_TIMESLOTS.values())
    user_counts = {timeslot: len(reaction_counts[day_name][timeslot]) for timeslot in timeslots}
    not_voted = get_not_voted_users(not_available_users, available_users)
    
    max_count = max(user_counts.values()) if user_counts else 1
    if len(not_available_users) > max_count:
        max_count = len(not_available_users)
    if len(not_voted) > max_count:
        max_count = len(not_voted)

    # Create bar chart image using Pillow
    bar_spacing = 10
    width = (2 + len(timeslots)) * 100 + bar_spacing
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
            realname = getUserRealName(user)
            draw.text((x1 + 5, y1 + 10), realname, fill='white', font=font)

        # Draw the label for the timeslot
        draw.text((i * (bar_width + bar_spacing) + bar_spacing + 5, height - 20), timeslot, fill='black', font=font)

    i = len(timeslots)
    draw.text((i * (bar_width + bar_spacing) + bar_spacing + 5, height - 20), "Nicht verfügbar", fill='black', font=font)
    for j, user in enumerate(not_available_users):
        x1 = i * (bar_width + bar_spacing) + bar_spacing
        y1 = height - (j + 1) * (block_height + vertical_spacing) - 30
        x2 = x1 + bar_width
        y2 = y1 + block_height
        draw.rectangle([x1, y1, x2, y2], fill=(80, 80, 80))
        realname = getUserRealName(user)
        draw.text((x1 + 5, y1 + 10), realname, fill='white', font=font)


    i = len(timeslots) + 1
    draw.text((i * (bar_width + bar_spacing) + bar_spacing + 5, height - 20), "Nicht gevoted", fill='black', font=font)
    not_voted_nicknames = [user.name for user in not_voted]
    for j, user in enumerate(not_voted_nicknames):
        x1 = i * (bar_width + bar_spacing) + bar_spacing
        y1 = height - (j + 1) * (block_height + vertical_spacing) - 30
        x2 = x1 + bar_width
        y2 = y1 + block_height
        draw.rectangle([x1, y1, x2, y2], fill=(0, 0, 200))
        realname = getUserRealName(user)
        draw.text((x1 + 5, y1 + 10), realname, fill='white', font=font)

    draw.text((width // 2 - 50, 10), f'Slots für {day_name}', fill='black', font=font)
    image_path = f'{day_name}.png'
    image.save(image_path)

    channel = client.get_channel(CHANNEL_ID)
    if channel is not None:
        try:
            if prev_chart_id is not None:
                logging.warning(f"create new chart but prev_chart_id is not None")
            msg = await channel.send(file=discord.File(f'{day_name}.png'))
            prev_chart_id = msg.id
            logging.info(f"sent chart with id {prev_chart_id}")
        except Exception as e:
            logging.warning(f"could not send chart ({e})")

        os.remove(image_path)
    else:
        print("Failed to send barchart image, channel not found.")


logging.info(f"startup at {datetime.now(TIMEZONE)}")
client.run(TOKEN)
