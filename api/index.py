"""
Vercel Serverless Function entry point.
Exposes the FastAPI application instance for Vercel's Python runtime.
"""
import sys
import os

# Ensure project root is in Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.main import app

