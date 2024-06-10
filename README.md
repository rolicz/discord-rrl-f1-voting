# Discord Bot for RRL F1 Voting

The bot posts messages for each day to the channel (`CHANNEL_ID`) in the server (`GUILD_ID`).
This happens automatically each Sunday at 22:00, or using the `KW [num]` command.
Players react with available times (6️⃣, 7️⃣, 8️⃣) to messages.
Each day at 15:00, the bot counts the reactions and posts a chart to the channel.
One hour before the voting closes, players who did not vote get a private message as a reminder.

## Usage
Install requirements.

### Start
`python3 voting-f1.py -t TOKEN -g GUILD_ID -c CHANNEL_ID -r ROLE_ID -m MIN_NUM_RACERS`
- `TOKEN`: bot token
- `GUILD_ID`: server id
- `CHANNEL_ID`: channel id
- `ROLE_ID`: role id to be pinged
- `MIN_NUM_RACERS`: min number of racers for race to start
- `-d` (optional): debug logging

### Commands
- `start`
    - Create chart manually
- `KW [num]`
    - create new voting messages for KW

## Known Issues
- Only one week can be active.
- The current day is selected only by weekday and happily ignores the date.
