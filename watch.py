#!/usr/bin/env python3

import sys
import json
from time import strftime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.absolute()
LOG_FILE = f'{SCRIPT_DIR}/bgpls-receiver.log'

while True:
    try:
        line = sys.stdin.readline().strip()
        if not line:
            continue
            
        message = json.loads(line)
        log_message = f"{strftime('%H:%M:%S')} {json.dumps(message, indent=2)}\n"
        
        with open(LOG_FILE, 'a') as f:
            f.write(log_message)
        
    except Exception as e:
        with open(LOG_FILE, 'a') as f:
            f.write(f"Error: {str(e)}\n")
