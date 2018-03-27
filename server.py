#!/usr/bin/env python3
"""Autophon of the FabLab Sion."""

################################################################################
# IMPORTS                                                                      #
################################################################################

import os
import sys
import threading
import time

import requests
import RPi.GPIO as GPIO
from logzero import logger
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

# Whether a TTY is available
TTY = sys.stdin.isatty()

################################################################################
# GPIO                                                                         #
################################################################################

# GPIO mode
GPIO.setmode(GPIO.BOARD)

# Pins number
IO_DIAL = 11
IO_RING = 12
IO_PULSES = 13
IO_HANGER = 15
IO_PUSHER = 18

# Inputs
GPIO.setup(IO_DIAL, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(IO_PULSES, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(IO_HANGER, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(IO_PUSHER, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

# Outputs
GPIO.setup(IO_RING, GPIO.OUT)

################################################################################
# TELEGRAM                                                                     #
################################################################################

# Create a telegram client and start it
CLIENT = TelegramClient('fablab_telegram_client',
                        API_ID,
                        API_HASH,
                        update_workers=1,
                        spawn_read_thread=TTY)
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

    def __init__(self, *args, **kwargs):
        """Initialize the Ring."""
        threading.Thread.__init__(self, *args, **kwargs)
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

class Door(threading.Thread):

    """Class handling the opening of the door."""

    def __init__(self, *args, **kwargs):
        """Initialize the Door handler."""
        threading.Thread.__init__(self, *args, **kwargs)
        self._trigger = threading.Event()
        self.start()

    def run(self):
        """Code of the thread."""
        while True:
            self._trigger.wait()
            logger.info('Trying to open the door')
            with requests.Session() as s:
                s.post(EASYDOOR_LOGINURL, {'login_username': EASYDOOR_USERNAME,
                                        'login_password': EASYDOOR_PASSWORD})
                success = s.get(EASYDOOR_OPENDOOR).status_code == 200
                if success:
                    logger.info('Door opened')
                else:
                    logger.error('Failed to open the door')
            self._trigger.clear()

    def open(self):
        """Open the door."""
        self._trigger.set()

################################################################################
# OBJECTS                                                                      #
################################################################################

RING = Ring(daemon=True)
DOOR = Door(daemon=True)
HANGER = threading.Event()
PUSHER = threading.Event()

################################################################################
# FUNCTIONS                                                                    #
################################################################################

def input_triggered(channel):
    """Input triggered."""
    logger.debug("Input {} triggered".format(channel))
    if channel == IO_PUSHER:
        PUSHER.set()
        PUSHER.clear()
    elif channel == IO_HANGER:
        HANGER.set()
        HANGER.clear()

def open_door():
    """Open the door of the Espace Creation."""
    DOOR.open()

def ask_for_door():
    """Ask for opening the door through Autophon."""
    logger.info('Someone is ringing at the door')
    RING.start_ring()
    triggered = HANGER.wait(timeout=20)
    if triggered:
        logger.info('Someone picked up the phone')
        open_door()
    else:
        logger.warn('Nobody picked up the phone')
    RING.stop_ring()

################################################################################
# SCRIPT HANDLING                                                              #
################################################################################

def main():
    """Start the Autophon."""
    # Register GPIO events detection
    GPIO.add_event_detect(IO_PUSHER,
                          GPIO.RISING,
                          callback=input_triggered,
                          bouncetime=200)
    GPIO.add_event_detect(IO_HANGER,
                          GPIO.FALLING,
                          callback=input_triggered,
                          bouncetime=200)
    if TTY:
        # Wait for the exit command to stop
        while input() != 'exit':
            pass
    else:
        CLIENT.idle()

if __name__ == '__main__':
    try:
        logger.info('Starting the autophon')
        main()
    except KeyboardInterrupt:
        logger.info('Autophon stopped by the user')
    finally:
        logger.info('Clean up the GPIO')
        GPIO.cleanup()
