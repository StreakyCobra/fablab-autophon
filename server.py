#!/usr/bin/env python3
"""Telegram client for the FabLab Sion."""

################################################################################
# IMPORTS                                                                      #
################################################################################

import os
import threading
import time

import requests
import RPi.GPIO as GPIO
from telethon import TelegramClient, events

################################################################################
# CONFIGURATIONS                                                               #
################################################################################

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

################################################################################
# GPIO                                                                         #
################################################################################

# GPIO mode
GPIO.setmode(GPIO.BOARD)

# Pins number
IO_DIAL = 11
IO_PULSES = 13
IO_HANGER = 15
IO_RING = 12

# Inputs
GPIO.setup(IO_DIAL, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)    # Dialing
GPIO.setup(IO_PULSES, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)  # Dial pulses
GPIO.setup(IO_HANGER, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)  # Hanger

# Outputs
GPIO.setup(IO_RING, GPIO.OUT)                               #  RING output

################################################################################
# TELEGRAM                                                                     #
################################################################################

# Create a telegram client and start it
CLIENT = TelegramClient('fablab_telegram_client',
                        API_ID,
                        API_HASH,
                        update_workers=1,
                        spawn_read_thread=False)
CLIENT.start()

@CLIENT.on(events.NewMessage(chats=BOT_ID, incoming=True))
def on_bot_message(_):
    """Handle messages from the door bot."""
    ask_for_door()

################################################################################
# CLASSES                                                                      #
################################################################################

class Ring(threading.Thread):

    """Class handling the ringing of the Autophon."""

    def __init__(self):
        """Initialize the Ring."""
        threading.Thread.__init__(self)
        self._ring = threading.Event()
        self.start()

    def run(self):
        """Code of the thread."""
        while True:
            self._ring.wait()
            while self._ring.is_set():
                GPIO.output(IO_RING, True)
                time.sleep(.5)
                GPIO.output(IO_RING, False)
                time.sleep(1.5)

    def start_ring(self):
        """Ring the phone."""
        self._ring.set()

    def stop_ring(self):
        """Stop the phone ringing."""
        self._ring.clear()

class Hanger(threading.Thread):

    """Class handling the hanger of the Autophon."""

    def __init__(self):
        """Initialize the Ring."""
        threading.Thread.__init__(self)
        self._ring = threading.Event()
        self.start()

    def run(self):
        """Code of the thread."""
        while True:
            self._ring.wait()
            while self._ring.is_set():
                GPIO.output(IO_RING, True)
                time.sleep(.5)
                GPIO.output(IO_RING, False)
                time.sleep(1.5)

    def start_ring(self):
        """Ring the phone."""
        self._ring.set()

    def stop_ring(self):
        """Stop the phone ringing."""
        self._ring.clear()

# Create thread objects
RING = Ring()
HANGER = Hanger()

################################################################################
# FUNCTIONS                                                                    #
################################################################################

def ask_for_door():
    """Ask for opening the door through Autophon."""
    RING.start_ring()
    channel = GPIO.wait_for_edge(IO_HANGER, GPIO.RISING, timeout=20000)
    if channel is not None:
        open_door()
    else:
        print(channel)
    RING.stop_ring()

def open_door():
    """Open the door of the Espace Creation."""
    with requests.Session() as s:
        s.post(EASYDOOR_LOGINURL, {'login_username': EASYDOOR_USERNAME,
                                   'login_password': EASYDOOR_PASSWORD})
        return s.get(EASYDOOR_OPENDOOR).status_code == 200

################################################################################
# SCRIPT                                                                       #
################################################################################

def main():
    """Start the Autophon."""
    CLIENT.idle()

def cleanup():
    """Cleanup the GPIO."""
    GPIO.cleanup()

if __name__ == '__main__':
    try:
        main()
    finally:
        cleanup()
