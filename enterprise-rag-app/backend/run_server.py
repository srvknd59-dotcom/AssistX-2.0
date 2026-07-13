"""Starts the backend directly — for running from an editor (Sublime Text's
Build/Ctrl+B, VS Code's Run, etc.) instead of a terminal command.

This does the same thing as: uvicorn app.main:app --reload --port 8000
but as a plain script you can hit "Run" on, regardless of what directory
your editor happens to launch it from.
"""

import os
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(THIS_DIR)
sys.path.insert(0, THIS_DIR)

import uvicorn  # noqa: E402

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
