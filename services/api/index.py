"""Vercel Python entrypoint: exposes the FastAPI ASGI app (see app/main.py)."""

from app.main import app

__all__ = ["app"]
