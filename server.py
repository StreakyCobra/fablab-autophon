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
from logzero import logger, loglevel
from telethon import TelegramClient, events

################################################################################
# CONFIGURATION                                                                #
################################################################################

# If an `.env` file is present, parse its content as environment variables
if os.path.exists('.env'):
    logger.info('Loading environment variables from `.env` file')
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
CODE_OPEN = os.environ['CODE_OPEN']
CODE_CANCEL = os.environ['CODE_CANCEL']

# Check whether it is an interactive session
IS_INTERACTIVE = sys.stdin.isatty()

# Set loglevel to INFO if not in an interactive session
loglevel(10 if IS_INTERACTIVE else 20)

# Pin numbers
IO_DIALER = 11
IO_RING = 12
IO_PULSES = 13
IO_HANGER = 15
IO_PUSHER = 18

################################################################################
# EVENTS                                                                       #
################################################################################

HANGER = threading.Event()
PUSHER = threading.Event()
DIALER = threading.Event()

def event_handler(channel):
    """Handle GPIOs events."""
    if channel == IO_HANGER and not GPIO.input(IO_HANGER):
        HANGER.set()
        time.sleep(.1)
        HANGER.clear()
    elif channel == IO_DIALER and GPIO.input(IO_DIALER):
        DIALER.set()
        time.sleep(.1)
        DIALER.clear()
    elif channel == IO_PUSHER and GPIO.input(IO_PUSHER):
        PUSHER.set()
        PUSHER.clear()
    else:
        return
    logger.debug("Event %s triggered (%s)",
                 channel,
                 "RISING" if GPIO.input(channel) else "FALLING")

################################################################################
# GPIO                                                                         #
################################################################################

# GPIO mode
GPIO.setmode(GPIO.BOARD)

# Inputs
GPIO.setup(IO_DIALER, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(IO_PULSES, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(IO_HANGER, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(IO_PUSHER, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

# Outputs
GPIO.setup(IO_RING, GPIO.OUT)

# Register GPIOs events detection
GPIO.add_event_detect(IO_DIALER,
                      GPIO.RISING,
                      callback=event_handler,
                      bouncetime=50)
GPIO.add_event_detect(IO_HANGER,
                      GPIO.FALLING,
                      callback=event_handler,
                      bouncetime=50)
GPIO.add_event_detect(IO_PUSHER,
                      GPIO.RISING,
                      callback=event_handler,
                      bouncetime=50)

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
            logger.info('Starting to ring the phone')
            while self._trigger.is_set():
                GPIO.output(IO_RING, True)
                time.sleep(.5)
                GPIO.output(IO_RING, False)
                time.sleep(1.5)
            logger.info('Stopping to ring the phone')

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

class Dial(threading.Thread):
    """Class handling the Dial of the Autophon."""
    def __init__(self, *args, **kwargs):
        """Initialize the Dial of the autophon."""
        threading.Thread.__init__(self, *args, **kwargs)
        self.start()

    def run(self):
        """Code of the thread."""
        while True:
            DIALER.wait()
            self.handle_code(self.listen())
            DIALER.clear()

    def listen(self):
        """Listen for digits."""
        number = ''
        last_digit = time.time()
        while True:
            while GPIO.input(IO_DIALER) == 0:
                if time.time() - last_digit >= 2:
                    return number
                time.sleep(0.01)
            last = time.time()
            once = False
            triggered = True
            digit = 0
            while not once or time.time() - last <= 0.2:
                if triggered and GPIO.input(IO_PULSES) == 0:
                    last = time.time()
                    once = True
                    triggered = False
                    digit += 1
                elif GPIO.input(IO_PULSES) == 1:
                    triggered = True
                time.sleep(0.01)
            number += str(digit % 10)
            last_digit = time.time()

    def handle_code(self, number):
        """Handle a entered code."""
        if number.startswith(CODE_OPEN) and len(number) == len(CODE_OPEN) + 1:
            until = time.time() + int(number[-1]) * 3600
            REQUEST.activate_auto(until)
            logger.info('Code %s: Automatic opening for %s hours', number, number[-1])
        elif number == CODE_CANCEL:
            REQUEST.cancel_auto()
            logger.info('Code %s: Cancel automatic opening', number)
        else:
            logger.info('Code %s: Invalid', number)
            return
        RING.start_ring()
        time.sleep(.5)
        RING.stop_ring()

class Request(threading.Thread):
    """Class handling the request to open the FabLab."""
    def __init__(self, *args, **kwargs):
        """Initialize the request handler."""
        threading.Thread.__init__(self, *args, **kwargs)
        self._trigger = threading.Event()
        self._timer = None
        self._delay = 20
        self._auto_until = None
        self.start()

    def run(self):
        """Code of the thread."""
        while True:
            self._trigger.wait()
            logger.info('Someone is requesting to open the door')
            # Handling automatic mode
            if self._auto_until is not None and (self._auto_until - time.time()) >= 0:
                logger.info('Automatic opening mode, opening the door')
                DOOR.open()
                RING.start_ring()
                time.sleep(.25)
                RING.stop_ring()
                self.cancel()
                return
            self._timer = threading.Timer(self._delay, self._timeout)
            self._timer.start()
            RING.start_ring()
            while self._trigger.is_set():
                if HANGER.wait(timeout=.5):
                    logger.info('The phone has been picked up, opening the door')
                    RING.stop_ring()
                    DOOR.open()
                    break
            else:
                RING.stop_ring()
            self.cancel()

    def _timeout(self):
        """Timer triggered."""
        logger.warning('The phone has NOT been picked up')
        self._trigger.clear()

    def request(self):
        """Request to open the door."""
        if self.is_requesting():
            self._timer.cancel()
            self._timer = threading.Timer(self._delay, self._timeout)
            self._timer.start()
        self._trigger.set()

    def cancel(self):
        """Cancel request to open the door."""
        self._timer.cancel()
        self._trigger.clear()

    def is_requesting(self):
        """Return true if a request is ongoing."""
        return self._trigger.is_set()

    def activate_auto(self, until):
        """Set automatic opening mode."""
        self._auto_until = until

    def cancel_auto(self):
        """Cancel automatic opening mode."""
        self._auto_until = None

class Direct(threading.Thread):
    """Class handling direct requests to open the FabLab."""
    def __init__(self, *args, **kwargs):
        """Initialize the handler of direct requests."""
        threading.Thread.__init__(self, *args, **kwargs)
        self.start()

    def run(self):
        """Code of the thread."""
        while True:
            PUSHER.wait()
            logger.info('Direct request to open the door')
            if REQUEST.is_requesting():
                REQUEST.cancel()
            DOOR.open()
            RING.start_ring()
            time.sleep(.25)
            RING.stop_ring()

# Create the threads
RING = Ring(daemon=True)
DOOR = Door(daemon=True)
DIAL = Dial(daemon=True)
REQUEST = Request(daemon=True)
DIRECT = Direct(daemon=True)

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
    logger.info('Message received from %s', BOT_ID)
    REQUEST.request()

################################################################################
# SCRIPT HANDLING                                                              #
################################################################################

def main():
    """Run the Autophon."""
    # If interactive session, wait for the 'exit' command to stop the server
    if IS_INTERACTIVE:
        logger.debug('Interactive session (type `exit` to quit)')
        while input() != 'exit':
            pass
    # Otherwise put the telegram client on idle mode to keep the server running
    else:
        logger.debug('Non-interactive session (stop the service to quit)')
        CLIENT.idle()

if __name__ == '__main__':
    try:
        logger.info('Autophon started')
        main()
    except KeyboardInterrupt:
        logger.warning('Keyboard interrupt')
    finally:
        logger.debug('Cleaning up GPIOs')
        GPIO.cleanup()
    logger.info('Autophon stopped')
