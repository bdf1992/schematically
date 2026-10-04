"""Runs the page half of the desktop launch seam in Chromium (desktop_launch_qa.py --page) so
scripts/qa.py, which lists bare file paths, covers it."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from desktop_launch_qa import page_check

if __name__ == '__main__':
    page_check()
