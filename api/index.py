"""
Vercel Serverless Function Entry Point
Wraps the FastAPI app for Vercel deployment.
Note: Vercel serverless functions have limitations:
- 50MB deployment size limit
- 10-second timeout (60s for Pro)
- Read-only file system except /tmp
- PostgreSQL required (SQLite won't persist)
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.api_v2 import app

# Vercel expects the app to be exported as 'app'
__all__ = ["app"]
