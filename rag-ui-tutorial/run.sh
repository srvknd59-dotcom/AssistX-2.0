#!/usr/bin/env bash
# One-command setup + launch for Mac and Linux. No Docker required.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "Installing dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo ""
  echo "Created .env — open it and add your OPENAI_API_KEY, then run ./run.sh again."
  exit 1
fi

echo "Starting the app..."
streamlit run app.py
