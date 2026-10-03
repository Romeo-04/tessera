from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS calls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    tier TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_tokens INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    latency_ms REAL NOT NULL,
    cost_usd REAL NOT NULL
);
"""


@dataclass(frozen=True)
class CallRecord:
    tier: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    cost_usd: float


class Telemetry:
    """Append-only log of every model call. The ablation table reads this."""

    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def record(self, rec: CallRecord) -> None:
        self._conn.execute(
            "INSERT INTO calls (ts, tier, model, prompt_tokens, completion_tokens,"
            " latency_ms, cost_usd) VALUES (?,?,?,?,?,?,?)",
            (
                time.time(),
                rec.tier,
                rec.model,
                rec.prompt_tokens,
                rec.completion_tokens,
                rec.latency_ms,
                rec.cost_usd,
            ),
        )
        self._conn.commit()

    def all(self) -> list[CallRecord]:
        rows = self._conn.execute(
            "SELECT tier, model, prompt_tokens, completion_tokens, latency_ms,"
            " cost_usd FROM calls ORDER BY id"
        ).fetchall()
        return [CallRecord(*r) for r in rows]

    def spent_since(self, ts: float) -> float:
        """Total USD recorded at or after `ts`. Feeds the daily spend ceiling."""
        (total,) = self._conn.execute(
            "SELECT COALESCE(SUM(cost_usd), 0) FROM calls WHERE ts >= ?", (ts,)
        ).fetchone()
        return float(total)
