#!/usr/bin/env python3
"""
Simple runner script for dossierhelper that works around installation issues.
"""

import sys
import os
from pathlib import Path

# Add the src directory to Python path so we can import dossierhelper
project_root = Path(__file__).parent
src_dir = project_root / "src"
sys.path.insert(0, str(src_dir))

# Now we can import and run the GUI
try:
    from dossierhelper.gui import main
    main()
except ImportError as e:
    print(f"Error importing dossierhelper: {e}")
    print(f"Make sure all dependencies are installed:")
    print("pip install python-dateutil rich pyyaml pdfminer.six")
    sys.exit(1)
except Exception as e:
    print(f"Error running dossierhelper: {e}")
    sys.exit(1)
