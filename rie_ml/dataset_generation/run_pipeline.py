#!/usr/bin/env python3
"""Script to run the dataset generation pipeline."""

import sys
from pathlib import Path

# Add parent directory to path to import dataset_generation module
sys.path.insert(0, str(Path(__file__).parent.parent))

from dataset_generation.pipeline import main

if __name__ == "__main__":
    main()
