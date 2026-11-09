"""Test-only environment bootstrap; CI must provide the same variable explicitly."""
import os
from pathlib import Path
from dotenv import load_dotenv

if "REACT_APP_BACKEND_URL" not in os.environ:
    load_dotenv(Path(__file__).resolve().parents[2] / "frontend" / ".env")

if not os.environ.get("REACT_APP_BACKEND_URL"):
    raise RuntimeError("REACT_APP_BACKEND_URL is required for integration tests")