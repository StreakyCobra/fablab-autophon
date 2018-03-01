#!/usr/bin/env python
"""Telegram client for the FabLab Sion."""

import os
from telethon import TelegramClient, events

# Set secrets
API_ID = os.environ['API_ID']
API_HASH = os.environ['API_HASH']
BOT_ID = os.environ['BOT_ID']
# Create telegram client and start it
CLIENT = TelegramClient('fablab_telegram_client',
                        API_ID,
                        API_HASH,
                        update_workers=1,
                        spawn_read_thread=False)
CLIENT.start()

@CLIENT.on(events.NewMessage(chats=BOT_ID, incoming=True))
def on_bot_message(event):
    """Handle messages from the door bot."""
    print(event.raw_text)

CLIENT.idle()