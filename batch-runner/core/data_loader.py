"""GDPVal Data Loader

This module is a compatibility wrapper for prepare_dataset.py.
All core functionality has been moved to prepare_dataset.py.

For new code, use prepare_dataset.py directly:
    from prepare_dataset import GDPValDataset, GDPValTask
"""

import sys
from pathlib import Path

# Add parent directory to path to import prepare_dataset
sys.path.insert(0, str(Path(__file__).parent.parent))

from prepare_dataset import GDPValDataset, GDPValTask

# Backward compatibility alias
GDPValDataLoader = GDPValDataset

__all__ = ['GDPValDataLoader', 'GDPValDataset', 'GDPValTask']
