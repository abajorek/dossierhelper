#!/bin/bash
# Launch the enhanced verbose Dossier Helper

cd "$(dirname "$0")"

# Set up Homebrew environment
eval "$(/opt/homebrew/bin/brew shellenv)"

# Activate virtual environment
source .venv/bin/activate

echo "🚀 Launching Enhanced Dossier Helper with Maximum Verbosity!"
echo "🎮 Strong Bad and RedLetterMedia commentary modes: ACTIVATED"
echo "🏷️ macOS Finder tagging confirmation: ENABLED"
echo "📊 Progress tracking with ETA and current file display: ON"
echo ""

# Run the application
python run_dossierhelper.py
