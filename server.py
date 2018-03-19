#!/usr/bin/env python3
"""Telegram client for the FabLab Sion."""

import os
import threading

import requests
from telethon import TelegramClient, events

# If an `.env` file is present, parse it contents in the environment variables
if os.path.exists('.env'):
    with open('.env', 'r') as f:
        for line in f.readlines():
            key, val = line.strip().split('=', maxsplit=1)
            os.environ[key.strip()] = val.strip()

# Get secrets
API_ID = os.environ['API_ID']
API_HASH = os.environ['API_HASH']
BOT_ID = os.environ['BOT_ID']
EASYDOOR_LOGINURL = os.environ['EASYDOOR_LOGINURL']
EASYDOOR_OPENDOOR = os.environ['EASYDOOR_OPENDOOR']
EASYDOOR_USERNAME = os.environ['EASYDOOR_USERNAME']
EASYDOOR_PASSWORD = os.environ['EASYDOOR_PASSWORD']

# Create a telegram client and start it
CLIENT = TelegramClient('fablab_telegram_client',
                        API_ID,
                        API_HASH,
                        update_workers=1,
                        spawn_read_thread=False)
CLIENT.start()


class Ring(threading.Thread):

    """Class handling the ringing of the Autophon."""

    def __init__(self):
        """Initialize the Ring."""
        threading.Thread.__init__(self)
        self._ring = threading.Event()
        self.start()

    def run(self):
        """Code of the thread."""
        self._ring.wait()
        print('RING')
        self._ring.clear()

    def ring(self):
        """Ring the phone."""
        self._ring.set()

RING = Ring()


def open_door():
    """Open the door of the Espace Creation."""
    with requests.Session() as s:
        s.post(EASYDOOR_LOGINURL, {'login_username': EASYDOOR_USERNAME,
                                   'login_password': EASYDOOR_PASSWORD})
        return s.get(EASYDOOR_OPENDOOR).status_code == 200


@CLIENT.on(events.NewMessage(chats=BOT_ID, incoming=True))
def on_bot_message(_):
    """Handle messages from the door bot."""
    RING.ring()


def main():
    """Start the Autophon."""
    CLIENT.idle()


if __name__ == '__main__':
    main()
