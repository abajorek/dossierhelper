#!/bin/bash
# Simple script to run dossierhelper

cd "$(dirname "$0")"

# Set up Homebrew environment
eval "$(/opt/homebrew/bin/brew shellenv)"

# Activate virtual environment
source .venv/bin/activate

# Run the application
python run_dossierhelper.py
