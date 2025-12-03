#!/usr/bin/env python3
"""
Convenience wrapper for running Motus from the repository

For development: python run.py
After installation: motus
"""
import sys
from pathlib import Path

# Add src to path for development (when not installed)
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from motus.run import main

if __name__ == '__main__':
    main()
