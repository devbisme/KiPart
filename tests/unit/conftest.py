import sys
import os
from pathlib import Path

# Add the directory for the code to be tested to the Python path
project_root = Path(__file__).parent.parent.parent / 'kipart'
sys.path.insert(0, str(project_root))
