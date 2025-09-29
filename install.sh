#!/bin/bash

# Dossier Helper Installation Script with Google Drive Support

echo "🚀 Dossier Helper Installation"
echo "================================"
echo ""

# Check if we're in a virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Warning: You are not in a virtual environment."
    echo "It's recommended to use a virtual environment."
    echo ""
    read -p "Do you want to create one now? (y/n): " create_venv
    
    if [ "$create_venv" = "y" ] || [ "$create_venv" = "Y" ]; then
        echo "Creating virtual environment..."
        python3 -m venv .venv
        source .venv/bin/activate
        echo "✅ Virtual environment created and activated"
    else
        echo "Continuing without virtual environment..."
    fi
else
    echo "✅ Virtual environment detected: $VIRTUAL_ENV"
fi

echo ""
echo "📦 Installing base dependencies..."
pip install -e .

echo ""
read -p "Do you want to install Google Drive support? (y/n): " install_gdrive

if [ "$install_gdrive" = "y" ] || [ "$install_gdrive" = "Y" ]; then
    echo "☁️  Installing Google Drive dependencies..."
    pip install -e ".[gdrive]"
    echo ""
    echo "✅ Google Drive support installed!"
    echo ""
    echo "📚 Next steps for Google Drive:"
    echo "1. Set up OAuth credentials in Google Cloud Console"
    echo "2. Read docs/GOOGLE_DRIVE_SETUP.md for detailed instructions"
    echo "3. Create ~/.dossierhelper directory for credentials"
    echo "4. Update example_config.yaml with your Google Drive settings"
else
    echo "⏭️  Skipping Google Drive support"
fi

echo ""
# Check if running on macOS
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "🍎 macOS detected - Finder tags support available"
    read -p "Do you want to install macOS-specific features? (y/n): " install_mac
    
    if [ "$install_mac" = "y" ] || [ "$install_mac" = "Y" ]; then
        echo "🍎 Installing macOS dependencies..."
        pip install -e ".[mac]"
        echo "✅ macOS support installed!"
    fi
fi

echo ""
echo "🎉 Installation complete!"
echo ""
echo "To run Dossier Helper:"
echo "  python run_dossierhelper.py"
echo ""
echo "Or use the command:"
echo "  dossierhelper"
echo ""
echo "📖 Documentation:"
echo "  - Main README: README.md"
echo "  - Google Drive Setup: docs/GOOGLE_DRIVE_SETUP.md"
echo ""
echo "🎮 Ready to scan and classify your academic files!"
echo "💪 Strong Bad approved! Let's do this!"
