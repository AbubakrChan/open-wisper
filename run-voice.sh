#!/bin/bash
# Wrapper script for Shortcuts - sets correct paths
export PATH="/opt/homebrew/bin:$PATH"
export PYTHONPATH="/Users/chan/Library/Python/3.9/lib/python/site-packages:$PYTHONPATH"
/Library/Developer/CommandLineTools/usr/bin/python3 /Users/chan/voice-transcriber/voice.py
