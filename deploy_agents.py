"""Backward-compatible entrypoint delegating to deployment/deploy_agents.py."""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from deployment.deploy_agents import deploy, parse_args

if __name__ == "__main__":
    args = parse_args()
    deploy(target=args.target, project_id=args.project, location=args.location)
