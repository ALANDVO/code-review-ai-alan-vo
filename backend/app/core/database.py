import os
import sqlite3
import json
from contextlib import contextmanager
from typing import Generator, List, Dict, Any, Optional
from datetime import datetime, timezone
import uuid


def get_utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self.init_schema()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self.transaction() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reviews (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    language TEXT NOT NULL,
                    review_type TEXT NOT NULL,
                    focus_areas TEXT NOT NULL,
                    code_snippet TEXT NOT NULL,
                    diff_text TEXT,
                    total_findings INTEGER NOT NULL DEFAULT 0,
                    critical_count INTEGER NOT NULL DEFAULT 0,
                    high_count INTEGER NOT NULL DEFAULT 0,
                    medium_count INTEGER NOT NULL DEFAULT 0,
                    low_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    advisory_llm_used INTEGER NOT NULL DEFAULT 0,
                    provider TEXT NOT NULL DEFAULT 'offline-engine'
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS findings (
                    id TEXT PRIMARY KEY,
                    review_id TEXT NOT NULL,
                    line_number INTEGER NOT NULL,
                    severity TEXT NOT NULL,
                    category TEXT NOT NULL,
                    cwe TEXT,
                    message TEXT NOT NULL,
                    suggestion TEXT,
                    rule_id TEXT,
                    advisory_note TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(review_id) REFERENCES reviews(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS eval_runs (
                    id TEXT PRIMARY KEY,
                    trigger TEXT NOT NULL,
                    total_samples INTEGER NOT NULL,
                    true_positives INTEGER NOT NULL,
                    false_positives INTEGER NOT NULL,
                    false_negatives INTEGER NOT NULL,
                    precision REAL NOT NULL,
                    recall REAL NOT NULL,
                    f1_score REAL NOT NULL,
                    mean_latency_ms REAL NOT NULL,
                    status TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    created_by TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    user_role TEXT NOT NULL,
                    action TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT,
                    details TEXT,
                    ip_address TEXT
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_reviews_created ON reviews(created_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_findings_review ON findings(review_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_eval_runs_created ON eval_runs(created_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(timestamp DESC)")

    def insert_review(self, review_data: Dict[str, Any], findings_data: List[Dict[str, Any]]) -> str:
        review_id = review_data.get("id") or str(uuid.uuid4())
        now = get_utc_now_iso()
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO reviews (
                    id, title, language, review_type, focus_areas, code_snippet,
                    diff_text, total_findings, critical_count, high_count, medium_count,
                    low_count, created_at, created_by, advisory_llm_used, provider
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    review_id,
                    review_data.get("title", "Code Review"),
                    review_data.get("language", "python"),
                    review_data.get("review_type", "full_file"),
                    review_data.get("focus_areas", "all"),
                    review_data.get("code_snippet", ""),
                    review_data.get("diff_text", ""),
                    len(findings_data),
                    sum(1 for f in findings_data if f.get("severity") == "critical"),
                    sum(1 for f in findings_data if f.get("severity") == "high"),
                    sum(1 for f in findings_data if f.get("severity") == "medium"),
                    sum(1 for f in findings_data if f.get("severity") == "low"),
                    review_data.get("created_at", now),
                    review_data.get("created_by", "anonymous"),
                    1 if review_data.get("advisory_llm_used") else 0,
                    review_data.get("provider", "offline-engine"),
                ),
            )
            for f in findings_data:
                finding_id = f.get("id") or str(uuid.uuid4())
                conn.execute(
                    """
                    INSERT INTO findings (
                        id, review_id, line_number, severity, category, cwe,
                        message, suggestion, rule_id, advisory_note, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        finding_id,
                        review_id,
                        f.get("line_number", 1),
                        f.get("severity", "medium"),
                        f.get("category", "bug"),
                        f.get("cwe"),
                        f.get("message", ""),
                        f.get("suggestion", ""),
                        f.get("rule_id", ""),
                        f.get("advisory_note", ""),
                        now,
                    ),
                )
        return review_id

    def get_review(self, review_id: str) -> Optional[Dict[str, Any]]:
        with self.transaction() as conn:
            cur = conn.execute("SELECT * FROM reviews WHERE id = ?", (review_id,))
            row = cur.fetchone()
            if not row:
                return None
            review = dict(row)
            f_cur = conn.execute("SELECT * FROM findings WHERE review_id = ? ORDER BY line_number ASC", (review_id,))
            review["findings"] = [dict(f) for f in f_cur.fetchall()]
            return review

    def list_reviews(self, limit: int = 50, offset: int = 0, language: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.transaction() as conn:
            if language:
                cur = conn.execute(
                    "SELECT * FROM reviews WHERE language = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (language.lower(), limit, offset),
                )
            else:
                cur = conn.execute(
                    "SELECT * FROM reviews ORDER BY created_at DESC LIMIT ? OFFSET ?",
                    (limit, offset),
                )
            return [dict(r) for r in cur.fetchall()]

    def count_reviews(self, language: Optional[str] = None) -> int:
        with self.transaction() as conn:
            if language:
                cur = conn.execute("SELECT COUNT(*) FROM reviews WHERE language = ?", (language.lower(),))
            else:
                cur = conn.execute("SELECT COUNT(*) FROM reviews")
            return cur.fetchone()[0]

    def insert_eval_run(self, eval_data: Dict[str, Any]) -> str:
        run_id = eval_data.get("id") or str(uuid.uuid4())
        now = get_utc_now_iso()
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO eval_runs (
                    id, trigger, total_samples, true_positives, false_positives,
                    false_negatives, precision, recall, f1_score, mean_latency_ms,
                    status, details_json, created_at, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    eval_data.get("trigger", "manual"),
                    eval_data.get("total_samples", 0),
                    eval_data.get("true_positives", 0),
                    eval_data.get("false_positives", 0),
                    eval_data.get("false_negatives", 0),
                    eval_data.get("precision", 0.0),
                    eval_data.get("recall", 0.0),
                    eval_data.get("f1_score", 0.0),
                    eval_data.get("mean_latency_ms", 0.0),
                    eval_data.get("status", "completed"),
                    json.dumps(eval_data.get("details", {})),
                    eval_data.get("created_at", now),
                    eval_data.get("created_by", "system"),
                ),
            )
        return run_id

    def list_eval_runs(self, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        with self.transaction() as conn:
            cur = conn.execute("SELECT * FROM eval_runs ORDER BY created_at DESC LIMIT ? OFFSET ?", (limit, offset))
            runs = []
            for row in cur.fetchall():
                d = dict(row)
                d["details"] = json.loads(d.pop("details_json"))
                runs.append(d)
            return runs

    def get_eval_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        with self.transaction() as conn:
            cur = conn.execute("SELECT * FROM eval_runs WHERE id = ?", (run_id,))
            row = cur.fetchone()
            if not row:
                return None
            d = dict(row)
            d["details"] = json.loads(d.pop("details_json"))
            return d

    def insert_audit_log(
        self,
        user_id: str,
        user_role: str,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        details: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> str:
        log_id = str(uuid.uuid4())
        now = get_utc_now_iso()
        with self.transaction() as conn:
            conn.execute(
                """
                INSERT INTO audit_logs (
                    id, timestamp, user_id, user_role, action,
                    resource_type, resource_id, details, ip_address
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (log_id, now, user_id, user_role, action, resource_type, resource_id, details, ip_address),
            )
        return log_id

    def list_audit_logs(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        with self.transaction() as conn:
            cur = conn.execute("SELECT * FROM audit_logs ORDER BY timestamp DESC LIMIT ? OFFSET ?", (limit, offset))
            return [dict(r) for r in cur.fetchall()]

    def delete_review(self, review_id: str) -> bool:
        with self.transaction() as conn:
            cur = conn.execute("DELETE FROM reviews WHERE id = ?", (review_id,))
            return cur.rowcount > 0

    def count_findings(self) -> int:
        with self.transaction() as conn:
            cur = conn.execute("SELECT COUNT(*) FROM findings")
            return cur.fetchone()[0]


_db_instance: Optional[Database] = None


def get_db(db_path: Optional[str] = None) -> Database:
    global _db_instance
    if _db_instance is None or (db_path and _db_instance.db_path != db_path):
        from .config import settings
        path = db_path or settings.database_path
        _db_instance = Database(path)
    return _db_instance
