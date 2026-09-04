"""Single-origin application and path layout for the packaged Windows Demo."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from .composition import create_demo_app
from .security import DemoClientAccessPolicy
from .standalone_settings import StandaloneSettings


class StandaloneResourceError(RuntimeError):
    def __init__(self, code: str, *, field: str) -> None:
        self.code = code
        self.field = field
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class StandaloneLayout:
    install_root: Path
    resource_root: Path
    runtime_root: Path
    config_path: Path
    frontend_root: Path

    @classmethod
    def discover(cls) -> StandaloneLayout:
        if getattr(sys, "frozen", False):
            install_root = Path(sys.executable).resolve().parent
            resource_root = Path(__file__).resolve().parents[1] / "repository"
        else:
            resource_root = Path(__file__).resolve().parents[3]
            install_root = resource_root / "demo"
        return cls.from_roots(install_root=install_root, resource_root=resource_root)

    @classmethod
    def from_roots(
        cls,
        *,
        install_root: Path,
        resource_root: Path,
    ) -> StandaloneLayout:
        install = install_root.resolve()
        resources = resource_root.resolve()
        return cls(
            install_root=install,
            resource_root=resources,
            runtime_root=install / "runtime" / "cnc-showcase",
            config_path=install / "config" / "demo-settings.json",
            frontend_root=resources / "demo" / "frontend" / "dist",
        )

    def validate(self) -> None:
        required = (
            (self.resource_root / "alembic.ini", "alembic.ini"),
            (self.resource_root / "backend" / "migrations" / "env.py", "migrations"),
            (self.resource_root / "schemas" / "json", "schemas"),
            (self.resource_root / "demo" / "data" / "cnc-showcase" / "manifest.json", "assets"),
            (self.frontend_root / "index.html", "frontend"),
            (self.config_path, "config"),
        )
        for path, field in required:
            if not path.exists():
                raise StandaloneResourceError("PACKAGE_RESOURCE_MISSING", field=field)
        try:
            self.runtime_root.mkdir(parents=True, exist_ok=True)
            probe = self.runtime_root / f".write-probe-{os.getpid()}"
            probe.write_text("ok\n", encoding="utf-8")
            probe.unlink()
        except OSError as error:
            raise StandaloneResourceError(
                "PACKAGE_RUNTIME_NOT_WRITABLE", field="runtime"
            ) from error


class DemoSpaStaticFiles(StaticFiles):
    """Serve the immutable Vite bundle with a safe history fallback."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            response = await super().get_response(path, scope)
        except HTTPException as error:
            if error.status_code != 404 or "." in Path(path).name:
                raise
            response = await super().get_response("index.html", scope)
        content_type = response.headers.get("content-type", "")
        if "text/html" in content_type:
            response.headers["Cache-Control"] = "no-store"
        else:
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response


def create_standalone_app(
    *,
    layout: StandaloneLayout,
    settings: StandaloneSettings,
    auto_resume_queued: bool = True,
) -> FastAPI:
    layout.validate()
    access_policy = DemoClientAccessPolicy(
        lan_enabled=settings.lan_mode,
        allowed_networks=settings.allowed_networks,
    )
    application = create_demo_app(
        repository_root=layout.resource_root,
        runtime_root=layout.runtime_root,
        auto_resume_queued=auto_resume_queued,
        client_access_policy=access_policy,
    )

    @application.get("/", include_in_schema=False)
    def demo_root() -> RedirectResponse:
        return RedirectResponse(url="/demo/", status_code=307)

    application.mount(
        "/demo",
        DemoSpaStaticFiles(directory=layout.frontend_root, html=True),
        name="demo-frontend",
    )
    application.state.demo_standalone_layout = layout
    application.state.demo_standalone_settings = settings
    return application


__all__ = [
    "DemoSpaStaticFiles",
    "StandaloneLayout",
    "StandaloneResourceError",
    "create_standalone_app",
]
