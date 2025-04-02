#!/bin/bash

cd "/Users/w3/downloads/_Transmission (temp)"
mkdir -p logs
source venv/bin/activate
nohup python3 app.py > logs/server.log 2>&1 &
echo $! > logs/server.pid 