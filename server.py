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
# CONFIGURATION                                                                #
################################################################################

# If an `.env` file is present, parse its content as environment variables
if os.path.exists('.env'):
    with open('.env', 'r') as f:
        for line in f.readlines():
            key, val = line.strip().split('=', maxsplit=1)
            os.environ[key.strip()] = val.strip()

# Get secrets from environment variables
API_ID = os.environ['API_ID']
API_HASH = os.environ['API_HASH']
BOT_ID = os.environ['BOT_ID']
EASYDOOR_LOGINURL = os.environ['EASYDOOR_LOGINURL']
EASYDOOR_OPENDOOR = os.environ['EASYDOOR_OPENDOOR']
EASYDOOR_USERNAME = os.environ['EASYDOOR_USERNAME']
EASYDOOR_PASSWORD = os.environ['EASYDOOR_PASSWORD']

# Check whether it is an interactive session
IS_INTERACTIVE = sys.stdin.isatty()

# Pin numbers
IO_DIAL = 11
IO_RING = 12
IO_PULSES = 13
IO_HANGER = 15
IO_PUSHER = 18

################################################################################
# EVENTS                                                                       #
################################################################################

HANGER = threading.Event()
PUSHER = threading.Event()

def event_handler(channel):
    """Handle GPIOs events."""
    logger.debug("Input %s triggered", channel)
    if channel == IO_HANGER:
        HANGER.set()
        HANGER.clear()
    elif channel == IO_PUSHER:
        PUSHER.set()
        PUSHER.clear()
    else:
        raise ValueError('Event not supported')

################################################################################
# GPIO                                                                         #
################################################################################

# GPIO mode
GPIO.setmode(GPIO.BOARD)

# Inputs
GPIO.setup(IO_DIAL, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(IO_PULSES, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(IO_HANGER, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(IO_PUSHER, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

# Outputs
GPIO.setup(IO_RING, GPIO.OUT)

# Register GPIOs events detection
GPIO.add_event_detect(IO_PUSHER,
                      GPIO.BOTH,
                      callback=event_handler,
                      bouncetime=200)
GPIO.add_event_detect(IO_HANGER,
                      GPIO.BOTH,
                      callback=event_handler,
                      bouncetime=200)

################################################################################
# CLASSES                                                                      #
################################################################################

class Ring(threading.Thread):
    """Class handling the ringing of the Autophon."""
    def __init__(self, *args, **kwargs):
        """Initialize the Ring handler."""
        threading.Thread.__init__(self, *args, **kwargs)
        self._trigger = threading.Event()
        self.start()

    def run(self):
        """Code of the thread."""
        while True:
            self._trigger.wait()
            while self._trigger.is_set():
                GPIO.output(IO_RING, True)
                time.sleep(.5)
                GPIO.output(IO_RING, False)
                time.sleep(1.5)

    def start_ring(self):
        """Make the phone ringing."""
        self._trigger.set()

    def stop_ring(self):
        """Stop the phone ringing."""
        self._trigger.clear()

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
            with requests.Session() as session:
                session.post(EASYDOOR_LOGINURL,
                             {'login_username': EASYDOOR_USERNAME,
                              'login_password': EASYDOOR_PASSWORD})
                success = session.get(EASYDOOR_OPENDOOR).status_code == 200
                if success:
                    logger.info('Door opened')
                else:
                    logger.error('Failed to open the door')

    def open(self):
        """Open the door."""
        self._trigger.set()
        self._trigger.clear()

class Direct(threading.Thread):
    """Class handling the direct request to open the FabLab."""
    def __init__(self, *args, **kwargs):
        """Initialize the handler of direct requests."""
        threading.Thread.__init__(self, *args, **kwargs)
        self.start()

    def run(self):
        """Code of the thread."""
        while True:
            PUSHER.wait()
            if REQUEST.is_requesting():
                REQUEST.cancel()
            DOOR.open()

class Request(threading.Thread):
    """Class handling the request to open the FabLab."""
    def __init__(self, *args, **kwargs):
        """Initialize the request handler."""
        threading.Thread.__init__(self, *args, **kwargs)
        self._trigger = threading.Event()
        self.start()

    def run(self):
        """Code of the thread."""
        while True:
            self._trigger.wait()
            timer = threading.Timer(20, self.cancel)
            timer.start()
            RING.start_ring()
            while self._trigger.is_set():
                if HANGER.wait(timeout=.5):
                    logger.info('Someone picked up the phone')
                    self._trigger.clear()
                    DOOR.open()
            timer.cancel()
            RING.stop_ring()

    def request(self):
        """Request to open the door."""
        self._trigger.set()

    def is_requesting(self):
        """Return true if a request is ongoing."""
        return self._trigger.is_set()

    def cancel(self):
        """Cancel request to open the door."""
        self._trigger.clear()

# Create the threads
RING = Ring(daemon=True)
DOOR = Door(daemon=True)
DIRECT = Direct(daemon=True)
REQUEST = Request(daemon=True)

################################################################################
# TELEGRAM                                                                     #
################################################################################

# Create a telegram client and start it
CLIENT = TelegramClient('fablab_telegram_client',
                        API_ID,
                        API_HASH,
                        update_workers=1,
                        spawn_read_thread=IS_INTERACTIVE)
CLIENT.start()

@CLIENT.on(events.NewMessage(chats=BOT_ID, incoming=True))
def on_bot_message(_):
    """Handle messages from the door bot."""
    logger.debug('Message received from %s', BOT_ID)
    REQUEST.request()

################################################################################
# SCRIPT HANDLING                                                              #
################################################################################

def main():
    """Run the Autophon."""
    # If interactive session, wait for the 'exit' command to stop the server
    if IS_INTERACTIVE:
        logger.debug('Interactive session')
        while input() != 'exit':
            pass
    # Otherwise put the telegram client on idle mode to keep the server running
    else:
        logger.debug('Non-interactive session')
        CLIENT.idle()

if __name__ == '__main__':
    try:
        logger.info('Starting the autophon')
        main()
    except KeyboardInterrupt:
        logger.warning('Autophon stopped by the user')
    finally:
        logger.debug('Clean up the GPIOs')
        GPIO.cleanup()
