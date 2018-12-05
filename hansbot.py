#!/usr/bin/env python3

import os
import time
import re
from slackclient import SlackClient
from sqlitedict import SqliteDict
from dateutil.relativedelta import relativedelta
import datetime 
from websocket import WebSocketConnectionClosedException

# instantiate Slack client
slack_client = SlackClient(os.environ.get('SLACK_BOT_TOKEN'))
# starterbot's user ID in Slack: value is assigned after the bot starts up
hansbot_id = None

# persistent storage
state = SqliteDict('./bot-state.sqlite', tablename='state', autocommit=True)
leaderboard_count = SqliteDict('./bot-state.sqlite', tablename='leaderboard_count', autocommit=True)
leaderboard_time = SqliteDict('./bot-state.sqlite', tablename='leaderboard_time', autocommit=True)

# constants
RTM_READ_DELAY = 1 # 1 second delay between reading from RTM
EXAMPLE_COMMAND = "do"
MENTION_REGEX = "^<@(|[WU].+?)>(.*)"
EMOJI_INVOCATION = ":hans:"

attrs = ['years', 'months', 'days', 'hours', 'minutes', 'seconds']
human_readable = lambda delta: ['%d %s' % (getattr(delta, attr), getattr(delta, attr) > 1 and attr or attr[:-1]) for attr in attrs if getattr(delta, attr)]

def claim_hans(originating_user, ts):
    if 'owner' not in state or state['owner'] is None:
        state['owner'] = originating_user
        state['ts'] = ts
        return '<@{}> has Hans!'.format(originating_user)
    elif originating_user == state['owner']:
        return 'Okay, fine, but you already _have_ Hans.'
    else:
        return '*Nope!* Sorry, <@{}> already has Hans.'.format(state['owner'])

def release_hans(originating_user, ts):
    if 'owner' not in state or state['owner'] is None:
        return 'Thanks, but nobody had Hans anyway.'
    elif originating_user == state['owner']:
        state['owner'] = None
        elapsed_time_s = ts - state['ts']
        elapsed_time_readable = ' '.join(human_readable(relativedelta(seconds=elapsed_time_s)))
        state['ts'] = ts
        leaderboard_count[originating_user] = leaderboard_count.get(originating_user, 0) + 1
        leaderboard_time[originating_user] = leaderboard_time.get(originating_user, 0) + elapsed_time_s
        return 'Thank you for releasing Hans after {}.'.format(elapsed_time_readable)
    else:
        return "Sorry, <@{}> already has Hans, so you can't just release it.".format(state['owner'])

def query_hans(originating_user, ts):
    if 'owner' not in state or state['owner'] is None:
        return "Hans is free."
    else:
        elapsed_time_s = ts - state['ts']
        elapsed_time_readable = ' '.join(human_readable(relativedelta(seconds=elapsed_time_s)))
        return "Hans belongs to <@{}>, who has had it for {}.".format(state['owner'], elapsed_time_readable)

def reset_hans(originating_user, ts):
    state['owner'] = None
    state['ts'] = ts
    return "<!here> be dragons! Hans has been forcefully reset by <@{}>!".format(originating_user)

def leaderboard(originating_user, ts):
    return '*Leaderboard results:*\n' + '\n'.join(['<@{}>: {} ({} uses)'.format(x, str(datetime.timedelta(seconds=leaderboard_time[x])), leaderboard_count[x]) for x in sorted(leaderboard_time, key=leaderboard_time.get, reverse=True)])


def parse_bot_commands(slack_events):
    """
        Parses a list of events coming from the Slack RTM API to find bot commands.
        If a bot command is found, this function returns a tuple of command and channel.
        If its not found, then this function returns None, None.
    """
    for event in slack_events:
        if event["type"] == "message" and not "subtype" in event:
            user_id, message = parse_direct_mention(event["text"])
            if user_id == hansbot_id:
                return message, event["channel"], event["user"], event["ts"]
            message = parse_emoji_mention(event["text"])
            if message:
                return message, event["channel"], event["user"], event["ts"]
    return None, None, None, None

def parse_direct_mention(message_text):
    """
        Finds a direct mention (a mention that is at the beginning) in message text
        and returns the user ID which was mentioned. If there is no direct mention, returns None
    """
    matches = re.search(MENTION_REGEX, message_text)
    # the first group contains the username, the second group contains the remaining message
    return (matches.group(1), matches.group(2).strip()) if matches else (None, None)

def parse_emoji_mention(message_text):
    matches = re.search(EMOJI_INVOCATION, message_text, re.IGNORECASE)
    return message_text if matches else None

def handle_command(command, channel, originating_user, ts):
    """
        Executes bot command if the command is known
    """
    sanitized_command = " ".join(command.split()).replace(':','').lower()
    # Default response is help text for the user
    default_response = "Not sure what you mean when you ask for: {}".format(sanitized_command)

    # Finds and executes the given command, filling in response
    response = None
    # Choose a command
    if re.search("claim", sanitized_command):
        response = claim_hans(originating_user, ts)
    elif re.search("clam", sanitized_command):
        response = claim_hans(originating_user, ts)
    elif sanitized_command.startswith("hans on"):
        response = claim_hans(originating_user, ts)
    elif sanitized_command.startswith("hans please"):
        response = claim_hans(originating_user, ts)
    elif re.search("get", sanitized_command):
        response = claim_hans(originating_user, ts)
    elif re.search("take", sanitized_command):
        response = claim_hans(originating_user, ts)
    elif re.search("give me", sanitized_command):
        response = "You could be a little more polite, you know."
    elif re.search("releas", sanitized_command):
        response = release_hans(originating_user, ts)
    elif sanitized_command.startswith("hans off"):
        response = release_hans(originating_user, ts)
    elif re.search("lose", sanitized_command):
        response = release_hans(originating_user, ts)
    elif sanitized_command.startswith("who"):
        response = query_hans(originating_user, ts)
    elif sanitized_command.startswith("query"):
        response = query_hans(originating_user, ts)
    elif sanitized_command.startswith("reset"):
        response = reset_hans(originating_user, ts)
    elif re.search("leaderboard", sanitized_command):
        response = leaderboard(originating_user, ts)
    elif sanitized_command.startswith("help"):
        response = "I'm afraid there's very little I can do to help _you_."
    elif sanitized_command.startswith("hans help"):
        response = "You're asking the wrong person."
    elif sanitized_command.startswith("hans up"):
        response = ":musical_note: If you're from the streets like me, put your :hans: up! :musical_note:"
    elif sanitized_command.startswith("hello"):
        response = "Oh, hello there!"
    elif sanitized_command.startswith("hi"):
        response = "Howdy!"
    elif sanitized_command.startswith("look"):
        response = "You are in a small, messy office. Along the wall there is a row of lab benches covered in wires."
    elif sanitized_command.startswith("inv"):
        response = "You have a Fluke 115 True RMS multimeter and some tangled leads."
    elif re.search("weather", sanitized_command):
        response = "Weather is happening! :weather:"
    elif re.search("kick", sanitized_command):
        response = "You're probably looking for `reset`, the use of which is highly discouraged."
    elif sanitized_command == "hans":
        response = "Holla."

    # Sends the response back to the channel
    slack_client.api_call(
        "chat.postMessage",
        channel=channel,
        text=response or default_response
    )

if __name__ == "__main__":
    if slack_client.rtm_connect(auto_reconnect=True, with_team_state=False):
        print("Hans Bot connected and running!")
        # Read bot's user ID by calling Web API method `auth.test`
        hansbot_id = slack_client.api_call("auth.test")["user_id"]
        while True:
            try:
                command, channel, originating_user, ts = parse_bot_commands(slack_client.rtm_read())
                if command:
                    handle_command(command, channel, originating_user, float(ts))
                time.sleep(RTM_READ_DELAY)
            except WebSocketConnectionClosedException as e:
                print(e)
                print('Caught websocket disconnect, reconnecting...')
                time.sleep(RTM_READ_DELAY)
                slack_client.rtm_connect(auto_reconnect=True, with_team_state=False)
            except Exception as e:
                print(e)
                time.sleep(RTM_READ_DELAY)
    else:
        print("Connection failed. Exception traceback printed above.")
