#!/bin/bash
# Replace with your actual test commands
uv run pytest -n=auto ../../../pandapower/tests/ || exit 1
# Add build steps if needed
# python -m build --wheel || exit 1
