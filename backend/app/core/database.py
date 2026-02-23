from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SqliteRepository:
    def __init__(self, db_path: Path | None = None) -> None:
        base_dir = Path(__file__).resolve().parents[2]
        data_dir = base_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path or data_dir / "system_design_lab.db"
        self._lock = threading.RLock()
        self.storage_mode = "sqlite_file"
        self._conn = self._new_connection(str(self.db_path))

    def init_schema(self) -> None:
        try:
            self._init_schema_inner()
        except sqlite3.OperationalError:
            # Some sandboxed environments reject sqlite file writes. Fall back to in-memory so the app still runs.
            with self._lock:
                self._conn.close()
                self._conn = self._new_connection(":memory:")
                self.storage_mode = "sqlite_memory_fallback"
            self._init_schema_inner()

    def _init_schema_inner(self) -> None:
        with self._lock, self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS test_runs (
                    run_id TEXT PRIMARY KEY,
                    scenario_id TEXT NOT NULL,
                    variant_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    stop_reason TEXT,
                    sandbox_profile TEXT NOT NULL,
                    sandbox_backend TEXT,
                    sandbox_limits_json TEXT,
                    load_profile_json TEXT NOT NULL,
                    safety_overrides_json TEXT
                );
                CREATE TABLE IF NOT EXISTS run_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    ts TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_run_events_run_id_id ON run_events(run_id, id);
                CREATE TABLE IF NOT EXISTS metric_samples (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    ts TEXT NOT NULL,
                    rps REAL NOT NULL,
                    latency_p50_ms REAL NOT NULL,
                    latency_p95_ms REAL NOT NULL,
                    latency_p99_ms REAL NOT NULL,
                    error_rate REAL NOT NULL,
                    cpu_pct REAL NOT NULL,
                    memory_mb REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_metric_samples_run_id_id ON metric_samples(run_id, id);
                CREATE TABLE IF NOT EXISTS recommendations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    recommendation_id TEXT NOT NULL,
                    rank_order INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_recommendations_run_id_rank ON recommendations(run_id, rank_order);

                CREATE TABLE IF NOT EXISTS scenarios (
                    scenario_id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    latest_requirement_set_id TEXT
                );

                CREATE TABLE IF NOT EXISTS requirement_sets (
                    requirement_set_id TEXT PRIMARY KEY,
                    scenario_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    functional_requirements_json TEXT NOT NULL,
                    non_functional_requirements_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_requirement_sets_scenario ON requirement_sets(scenario_id);

                CREATE TABLE IF NOT EXISTS architecture_variants (
                    variant_id TEXT PRIMARY KEY,
                    scenario_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    assumptions_json TEXT NOT NULL,
                    components_json TEXT NOT NULL,
                    target_profile_json TEXT NOT NULL,
                    rationale TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_variants_scenario ON architecture_variants(scenario_id);
                """
            )

    def _new_connection(self, target: str) -> sqlite3.Connection:
        conn = sqlite3.connect(target, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def create_run(self, record: dict[str, Any]) -> None:
        row = {
            "run_id": record["run_id"],
            "scenario_id": record["scenario_id"],
            "variant_id": record["variant_id"],
            "status": record["status"],
            "phase": record["phase"],
            "created_at": record["created_at"],
            "updated_at": record["updated_at"],
            "stop_reason": record.get("stop_reason"),
            "sandbox_profile": record["sandbox_profile"],
            "sandbox_backend": record.get("sandbox_backend"),
            "sandbox_limits_json": json.dumps(record.get("sandbox_limits") or {}),
            "load_profile_json": json.dumps(record["load_profile"]),
            "safety_overrides_json": json.dumps(record.get("safety_overrides") or {}),
        }
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO test_runs (
                    run_id, scenario_id, variant_id, status, phase, created_at, updated_at,
                    stop_reason, sandbox_profile, sandbox_backend, sandbox_limits_json,
                    load_profile_json, safety_overrides_json
                ) VALUES (
                    :run_id, :scenario_id, :variant_id, :status, :phase, :created_at, :updated_at,
                    :stop_reason, :sandbox_profile, :sandbox_backend, :sandbox_limits_json,
                    :load_profile_json, :safety_overrides_json
                )
                """,
                row,
            )

    def update_run(self, run_id: str, **fields: Any) -> dict[str, Any] | None:
        if not fields:
            return self.get_run(run_id)
        params = {"run_id": run_id, "updated_at": utc_now_iso()}
        sets = ["updated_at = :updated_at"]
        for key, val in fields.items():
            col = "sandbox_limits_json" if key == "sandbox_limits" else key
            if key == "sandbox_limits":
                val = json.dumps(val or {})
            params[col] = val
            sets.append(f"{col} = :{col}")
        with self._lock, self._conn:
            self._conn.execute(f"UPDATE test_runs SET {', '.join(sets)} WHERE run_id = :run_id", params)
        return self.get_run(run_id)

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM test_runs WHERE run_id = ?", (run_id,)).fetchone()
        if not row:
            return None
        return {
            "run_id": row["run_id"],
            "scenario_id": row["scenario_id"],
            "variant_id": row["variant_id"],
            "status": row["status"],
            "phase": row["phase"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "stop_reason": row["stop_reason"],
            "sandbox": {
                "profile": row["sandbox_profile"],
                "backend": row["sandbox_backend"],
                "limits": json.loads(row["sandbox_limits_json"] or "{}"),
            },
            "load_profile": json.loads(row["load_profile_json"] or "{}"),
            "safety_overrides": json.loads(row["safety_overrides_json"] or "{}") or None,
        }

    def append_event(self, run_id: str, event_type: str, payload: dict[str, Any]) -> int:
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT INTO run_events(run_id, ts, event_type, payload_json) VALUES (?, ?, ?, ?)",
                (run_id, utc_now_iso(), event_type, json.dumps(payload)),
            )
            return int(cur.lastrowid)

    def get_events(self, run_id: str, after_id: int = 0, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, run_id, ts, event_type, payload_json FROM run_events WHERE run_id = ? AND id > ? ORDER BY id ASC LIMIT ?",
                (run_id, after_id, limit),
            ).fetchall()
        return [
            {
                "id": int(r["id"]),
                "run_id": r["run_id"],
                "timestamp": r["ts"],
                "type": r["event_type"],
                "payload": json.loads(r["payload_json"]),
            }
            for r in rows
        ]

    def append_metric(self, run_id: str, sample: dict[str, Any]) -> int:
        ts = sample.get("timestamp") or utc_now_iso()
        m = sample["latency_ms"]
        with self._lock, self._conn:
            cur = self._conn.execute(
                """
                INSERT INTO metric_samples(run_id, ts, rps, latency_p50_ms, latency_p95_ms, latency_p99_ms, error_rate, cpu_pct, memory_mb)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    ts,
                    float(sample["rps"]),
                    float(m["p50"]),
                    float(m["p95"]),
                    float(m["p99"]),
                    float(sample["error_rate"]),
                    float(sample["cpu_pct"]),
                    float(sample["memory_mb"]),
                ),
            )
            return int(cur.lastrowid)

    def get_metric_events(self, run_id: str, after_id: int = 0, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT id, run_id, ts, rps, latency_p50_ms, latency_p95_ms, latency_p99_ms, error_rate, cpu_pct, memory_mb
                FROM metric_samples WHERE run_id = ? AND id > ? ORDER BY id ASC LIMIT ?
                """,
                (run_id, after_id, limit),
            ).fetchall()
        return [
            {
                "id": int(r["id"]),
                "type": "metric.aggregate",
                "run_id": r["run_id"],
                "timestamp": r["ts"],
                "metrics": {
                    "rps": float(r["rps"]),
                    "latency_ms": {"p50": float(r["latency_p50_ms"]), "p95": float(r["latency_p95_ms"]), "p99": float(r["latency_p99_ms"])},
                    "error_rate": float(r["error_rate"]),
                    "cpu_pct": float(r["cpu_pct"]),
                    "memory_mb": float(r["memory_mb"]),
                },
            }
            for r in rows
        ]

    def get_metric_series(self, run_id: str, limit: int = 240) -> dict[str, Any]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, ts, rps, latency_p95_ms, cpu_pct, memory_mb, error_rate FROM metric_samples WHERE run_id = ? ORDER BY id DESC LIMIT ?",
                (run_id, limit),
            ).fetchall()
        rows = list(reversed(rows))
        names = ("rps", "latency_p95_ms", "cpu_pct", "memory_mb", "error_rate")
        return {
            "run_id": run_id,
            "series": [{"name": n, "points": [[r["ts"], r[n]] for r in rows]} for n in names],
        }

    def summarize_run_metrics(self, run_id: str) -> dict[str, Any]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT rps, latency_p95_ms, latency_p99_ms, error_rate, cpu_pct, memory_mb FROM metric_samples WHERE run_id = ? ORDER BY id ASC",
                (run_id,),
            ).fetchall()
        if not rows:
            return {"sample_count": 0}
        vals = {k: [float(r[k]) for r in rows] for k in rows[0].keys()}
        return {
            "sample_count": len(rows),
            "avg_rps": sum(vals["rps"]) / len(vals["rps"]),
            "max_rps": max(vals["rps"]),
            "avg_latency_p95_ms": sum(vals["latency_p95_ms"]) / len(vals["latency_p95_ms"]),
            "max_latency_p95_ms": max(vals["latency_p95_ms"]),
            "max_latency_p99_ms": max(vals["latency_p99_ms"]),
            "avg_error_rate": sum(vals["error_rate"]) / len(vals["error_rate"]),
            "max_error_rate": max(vals["error_rate"]),
            "avg_cpu_pct": sum(vals["cpu_pct"]) / len(vals["cpu_pct"]),
            "max_cpu_pct": max(vals["cpu_pct"]),
            "avg_memory_mb": sum(vals["memory_mb"]) / len(vals["memory_mb"]),
            "max_memory_mb": max(vals["memory_mb"]),
            "latest": {
                "rps": vals["rps"][-1],
                "latency_p95_ms": vals["latency_p95_ms"][-1],
                "latency_p99_ms": vals["latency_p99_ms"][-1],
                "error_rate": vals["error_rate"][-1],
                "cpu_pct": vals["cpu_pct"][-1],
                "memory_mb": vals["memory_mb"][-1],
            },
        }

    def replace_recommendations(self, run_id: str, items: list[dict[str, Any]]) -> None:
        now = utc_now_iso()
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM recommendations WHERE run_id = ?", (run_id,))
            for i, item in enumerate(items, start=1):
                self._conn.execute(
                    "INSERT INTO recommendations(run_id, recommendation_id, rank_order, created_at, payload_json) VALUES (?, ?, ?, ?, ?)",
                    (run_id, item["recommendation_id"], i, now, json.dumps(item)),
                )

    def get_recommendations(self, run_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT payload_json FROM recommendations WHERE run_id = ? ORDER BY rank_order ASC",
                (run_id,),
            ).fetchall()
        return [json.loads(r["payload_json"]) for r in rows]

    def create_scenario(self, row: dict[str, Any]) -> dict[str, Any]:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO scenarios(scenario_id, project_id, name, description, status, created_at, updated_at, latest_requirement_set_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["scenario_id"],
                    row["project_id"],
                    row["name"],
                    row.get("description"),
                    row["status"],
                    row["created_at"],
                    row["updated_at"],
                    row.get("latest_requirement_set_id"),
                ),
            )
        return self.get_scenario(row["scenario_id"])  # type: ignore[return-value]

    def update_scenario(self, scenario_id: str, **fields: Any) -> dict[str, Any] | None:
        if not fields:
            return self.get_scenario(scenario_id)
        params: dict[str, Any] = {"scenario_id": scenario_id, "updated_at": utc_now_iso()}
        sets = ["updated_at = :updated_at"]
        for key, val in fields.items():
            params[key] = val
            sets.append(f"{key} = :{key}")
        with self._lock, self._conn:
            self._conn.execute(f"UPDATE scenarios SET {', '.join(sets)} WHERE scenario_id = :scenario_id", params)
        return self.get_scenario(scenario_id)

    def get_scenario(self, scenario_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM scenarios WHERE scenario_id = ?", (scenario_id,)).fetchone()
        if not row:
            return None
        return {
            "scenario_id": row["scenario_id"],
            "project_id": row["project_id"],
            "name": row["name"],
            "description": row["description"],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "latest_requirement_set_id": row["latest_requirement_set_id"],
        }

    def create_requirement_set(self, row: dict[str, Any]) -> dict[str, Any]:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO requirement_sets(requirement_set_id, scenario_id, created_at, functional_requirements_json, non_functional_requirements_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    row["requirement_set_id"],
                    row["scenario_id"],
                    row["created_at"],
                    json.dumps(row.get("functional_requirements") or []),
                    json.dumps(row.get("non_functional_requirements") or {}),
                ),
            )
        self.update_scenario(
            row["scenario_id"],
            latest_requirement_set_id=row["requirement_set_id"],
            status="requirements_defined",
        )
        return self.get_requirement_set(row["requirement_set_id"])  # type: ignore[return-value]

    def get_requirement_set(self, requirement_set_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM requirement_sets WHERE requirement_set_id = ?",
                (requirement_set_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "requirement_set_id": row["requirement_set_id"],
            "scenario_id": row["scenario_id"],
            "created_at": row["created_at"],
            "functional_requirements": json.loads(row["functional_requirements_json"] or "[]"),
            "non_functional_requirements": json.loads(row["non_functional_requirements_json"] or "{}"),
        }

    def get_latest_requirement_set_for_scenario(self, scenario_id: str) -> dict[str, Any] | None:
        scenario = self.get_scenario(scenario_id)
        if not scenario or not scenario.get("latest_requirement_set_id"):
            return None
        return self.get_requirement_set(str(scenario["latest_requirement_set_id"]))

    def create_architecture_variant(self, row: dict[str, Any]) -> dict[str, Any]:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO architecture_variants(variant_id, scenario_id, name, created_at, assumptions_json, components_json, target_profile_json, rationale)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["variant_id"],
                    row["scenario_id"],
                    row["name"],
                    row["created_at"],
                    json.dumps(row.get("assumptions") or []),
                    json.dumps(row.get("components") or []),
                    json.dumps(row.get("target_profile") or {}),
                    row.get("rationale"),
                ),
            )
        self.update_scenario(row["scenario_id"], status="designed")
        return self.get_variant(row["variant_id"])  # type: ignore[return-value]

    def list_variants(self, scenario_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM architecture_variants WHERE scenario_id = ? ORDER BY created_at DESC",
                (scenario_id,),
            ).fetchall()
        return [self._variant_row_to_dict(r) for r in rows]

    def get_variant(self, variant_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM architecture_variants WHERE variant_id = ?", (variant_id,)).fetchone()
        return self._variant_row_to_dict(row) if row else None

    def _variant_row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "variant_id": row["variant_id"],
            "scenario_id": row["scenario_id"],
            "name": row["name"],
            "created_at": row["created_at"],
            "assumptions": json.loads(row["assumptions_json"] or "[]"),
            "components": json.loads(row["components_json"] or "[]"),
            "target_profile": json.loads(row["target_profile_json"] or "{}"),
            "rationale": row["rationale"],
        }
