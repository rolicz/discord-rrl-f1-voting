# Discord Bot for RRL F1 Voting

Create a new KW (see commands). The bot posts messages for each day to the channel (`CHANNEL_ID`) in the server (`GUILD_ID`).
Players react with available times (6️⃣, 7️⃣, 8️⃣) to messages.
Each day at 15:00, the bot counts the reactions and posts a chart to the channel.


## Usage
Install requirements.

### Start
`python3 voting-f1.py -t TOKEN -g GUILD_ID -c CHANNEL_ID -r MIN_NUM_RACERS`
- `TOKEN`: bot token
- `GUILD_ID`: server id
- `CHANNEL_ID`: channel id
- `MIN_NUM_RACERS`: min number of racers for race to start
- `-d` (optional): debug logging

### Commands
- `start`
    - Create chart manually
- `KW [num]`
    - create new voting messages for KW
