import sys
import os
from pathlib import Path

# Add the parent directory (which contains kipart) to the Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
