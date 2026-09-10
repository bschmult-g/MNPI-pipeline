"""Lightweight root launcher for the MNPI Ingestion & Compliance Demonstration Server.

Delegates to demo/demo_server.py while maintaining backward compatibility.
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from demo.demo_server import app, run

if __name__ == "__main__":
    run()
