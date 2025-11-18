"""
Command-line interface for Motus
"""
import sys
from pathlib import Path

# Add parent directory to path to import run module
sys.path.insert(0, str(Path(__file__).parent.parent))

from run import main as run_main


def main():
    """Entry point for the motus CLI command"""
    run_main()


if __name__ == '__main__':
    main()
