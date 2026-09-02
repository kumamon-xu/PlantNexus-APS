"""ASGI entry point for the localhost-only CNC Demo."""

from .composition import create_demo_app


app = create_demo_app()


__all__ = ["app"]
