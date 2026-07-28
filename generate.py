"""
BrandForge entrypoint.

Usage:
    python generate.py
    python generate.py --category ai --top 20
    python generate.py categories
    python generate.py logo Lumivo
    python generate.py check Merixa
"""

from __future__ import annotations

from brandforge.cli import app

if __name__ == "__main__":
    app()
