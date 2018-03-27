#!/usr/bin/env bash

# Create a python virtual environment if it does not exist
if [ ! -d "venv" ]; then
    python3 -m venv venv
    pip install -r requirements.txt
fi

# Activate the python virtual environment
source ./venv/bin/activate

# Upgrade python dependencies
pip-sync

# Run the server
python3 server.py
