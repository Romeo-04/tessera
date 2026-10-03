"""HTTP surface. Two live endpoints, split exactly at the privacy gate.

  POST /api/read     photographs -> named, coded drugs     (perception)
  POST /api/assess   {"codes": [...]} -> cited risks by code (reasoning)

The browser holds the names. It sends `/api/assess` a body whose schema
forbids every field except `codes` and forbids any code that is not
`RXCUI:<digits>`, so a name in the request is a 422 at the boundary rather
than a value some handler is trusted to ignore. Names are re-joined on the
client, which had them all along.

`/api/read` is honest about being on the other side: the photographs reach
it, because perception runs in the cloud today (see the README's deployment
table). They are written to a temporary directory for the one call and
deleted before the response is sent.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from tessera.api.limits import RateLimiter, SpendCeiling
from tessera.errors import RateLimitedError, TesseraError, UpstreamError
from tessera.pipeline import Perception
from tessera.schemas import RXCUI_RE, Candidate, CodeSet, SessionResult

log = logging.getLogger("tessera.api")

MAX_PHOTOS = 8
MAX_PHOTO_BYTES = 8 * 1024 * 1024
MAX_CODES = 40

# Magic numbers, not the client's Content-Type, decide what an upload is.
IMAGE_SIGNATURES = {
    b"\xff\xd8\xff": ".jpg",
    b"\x89PNG\r\n\x1a\n": ".png",
}


def _image_suffix(head: bytes) -> str | None:
    for sig, suffix in IMAGE_SIGNATURES.items():
        if head.startswith(sig):
            return suffix
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return ".webp"
    return None


class AssessRequest(BaseModel):
    """The privacy gate, as an HTTP schema. Codes, and nothing else."""

    model_config = ConfigDict(extra="forbid")

    codes: list[str] = Field(..., max_length=MAX_CODES)

    @field_validator("codes")
    @classmethod
    def _only_rxcui(cls, v: list[str]) -> list[str]:
        for c in v:
            if not RXCUI_RE.match(c):
                raise ValueError("codes must match ^RXCUI:\\d+$")
        return v


class ReadDrug(BaseModel):
    raw_name: str
    strength: str | None
    form: str | None
    rxcui: str | None
    display_name: str | None
    confidence: float
    in_formulary: bool


class ConfirmationOut(BaseModel):
    raw_name: str
    options: list[Candidate]


class ReadResponse(BaseModel):
    drugs: list[ReadDrug]
    excluded: list[str]
    confirmations: list[ConfirmationOut]
    unreadable: bool


@dataclass
class Deps:
    read_fn: Callable[[list[Path]], Perception] | None
    assess_fn: Callable[[CodeSet], SessionResult] | None
    limiter: RateLimiter
    ceiling: SpendCeiling | None
    alerts_path: Path | None

    @property
    def live(self) -> bool:
        return self.read_fn is not None and self.assess_fn is not None


def _fallback(status: int, detail: str) -> JSONResponse:
    """Every refusal of a live call tells the client the demo still works."""
    return JSONResponse(status_code=status, content={"detail": detail, "fallback": "demo"})


def default_deps() -> Deps:
    """Wire the real pipeline when credentials and the built corpus exist.

    Either missing is not an error: the API still serves /health and alerts,
    and the live routes answer 503 with a pointer to the demo.
    """
    from tessera.config import get_settings

    try:
        settings = get_settings()
    except Exception:  # no NEBIUS_API_KEY - the common case for a fresh clone
        log.warning("no NEBIUS_API_KEY: live routes disabled, demo only")
        return Deps(None, None, RateLimiter(6, 600), None, Path("data/watch/alerts.json"))

    limiter = RateLimiter(settings.calls_per_window, settings.window_seconds)
    alerts = settings.data_dir / "watch" / "alerts.json"
    try:
        from tessera.cli import _load_corpus
        from tessera.pipeline import assess, perceive
        from tessera.router import Router

        index, table, formulary, covered = _load_corpus(settings)
        router = Router()
    except FileNotFoundError as exc:
        log.warning("corpus not built (%s): live routes disabled", exc)
        return Deps(None, None, limiter, None, alerts)

    return Deps(
        read_fn=lambda paths: perceive(paths, router, formulary),
        assess_fn=lambda codes: assess(codes, index, table, router, covered or None),
        limiter=limiter,
        ceiling=SpendCeiling(router.spent_since, settings.daily_usd),
        alerts_path=alerts,
    )


def create_app(deps: Deps | None = None) -> FastAPI:
    deps = deps or default_deps()
    app = FastAPI(title="Tessera", docs_url="/api/docs", openapi_url="/api/openapi.json")

    origins = os.environ.get("TESSERA_CORS_ORIGINS", "*").split(",")
    app.add_middleware(
        CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    def guard(request: Request) -> JSONResponse | None:
        """Checks every live call passes before any model is touched."""
        if not deps.live:
            return _fallback(503, "Live checking is not configured on this server.")
        caller = request.client.host if request.client else "unknown"
        if not deps.limiter.allow(caller):
            return _fallback(429, "Too many checks from this connection. "
                                  "Try again in a few minutes.")
        if deps.ceiling is not None and deps.ceiling.exceeded():
            return _fallback(429, "Today's live-checking budget is used up. "
                                  "It resets at midnight UTC.")
        return None

    def upstream(fn):
        try:
            return fn(), None
        except RateLimitedError:
            return None, _fallback(429, "The model service is rate-limiting us. "
                                        "Nothing was checked.")
        except UpstreamError:
            # No partial body: a half-finished list would look like a whole one.
            return None, JSONResponse(status_code=502, content={
                "detail": "The model service failed, so nothing was checked."})
        except TesseraError as exc:
            return None, JSONResponse(status_code=500, content={"detail": str(exc)})

    @app.get("/health")
    def health():
        return {"status": "ok", "live": deps.live}

    @app.post("/api/assess", response_model=SessionResult)
    def assess_route(body: AssessRequest, request: Request):
        if (refused := guard(request)) is not None:
            return refused
        result, err = upstream(lambda: deps.assess_fn(CodeSet(codes=body.codes)))
        return err or result

    @app.post("/api/read", response_model=ReadResponse)
    async def read_route(request: Request, photos: list[UploadFile] = File(...)):
        if len(photos) > MAX_PHOTOS:
            return JSONResponse(status_code=422, content={
                "detail": f"At most {MAX_PHOTOS} photographs per check."})
        blobs: list[tuple[bytes, str]] = []
        for f in photos:
            data = await f.read(MAX_PHOTO_BYTES + 1)
            if len(data) > MAX_PHOTO_BYTES:
                return JSONResponse(status_code=422, content={
                    "detail": f"{f.filename}: larger than 8 MB."})
            suffix = _image_suffix(data[:16])
            if suffix is None:
                return JSONResponse(status_code=422, content={
                    "detail": f"{f.filename}: not a JPEG, PNG or WebP image."})
            blobs.append((data, suffix))

        if (refused := guard(request)) is not None:
            return refused

        with tempfile.TemporaryDirectory(prefix="tessera-") as tmp:
            paths = []
            for i, (data, suffix) in enumerate(blobs):
                p = Path(tmp) / f"label-{i}{suffix}"
                p.write_bytes(data)
                paths.append(p)
            perception, err = upstream(lambda: deps.read_fn(paths))
        if err:
            return err

        return ReadResponse(
            drugs=[ReadDrug(
                raw_name=d.record.raw_name, strength=d.record.strength,
                form=d.record.form, rxcui=d.rxcui, display_name=d.display_name,
                confidence=d.confidence, in_formulary=d.in_formulary,
            ) for d in perception.drugs],
            excluded=perception.excluded,
            confirmations=[ConfirmationOut(raw_name=c.raw_name, options=c.options)
                           for c in perception.confirmations],
            unreadable=perception.unreadable,
        )

    @app.get("/api/alerts")
    def alerts():
        """The whole formulary's alerts. The client filters to its own codes."""
        path = deps.alerts_path
        if path is None or not path.exists():
            return {"generated_at": None, "alerts": [], "unchecked": []}
        return json.loads(path.read_text(encoding="utf-8"))

    return app
