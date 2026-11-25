"""SQLite-backed Human-in-the-Loop (HITL) Redline Approval Store with RBAC enforcement.

The AI agent can stage redline proposals (`PENDING_APPROVAL`), but ONLY an authorized
human Legal Counsel or General Counsel can approve or reject them.
"""

from __future__ import annotations

import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "legal_approvals.db"

APPROVER_ROLES = {"legal_counsel", "general_counsel"}


class RBACPermissionError(PermissionError):
    """Raised when a user persona lacks permission to execute a legal sign-off."""


class ApprovalStore:
    """Manages staged HITL contract redline approvals and audit logs."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = Path(db_path or os.getenv("LEGAL_DB_PATH") or DEFAULT_DB_PATH)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        conn = self._connect()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS redline_approvals (
                    approval_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    contract_id TEXT NOT NULL,
                    counterparty TEXT NOT NULL,
                    clause_title TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    playbook_rule_id TEXT NOT NULL,
                    original_text TEXT NOT NULL,
                    proposed_redline TEXT NOT NULL,
                    rationale TEXT NOT NULL,
                    status TEXT NOT NULL,
                    decided_by_role TEXT,
                    decided_at TEXT,
                    reviewer_note TEXT
                );
                """
            )
            conn.commit()
        finally:
            conn.close()

    def stage_redline(
        self,
        contract_id: str,
        counterparty: str,
        clause_title: str,
        risk_level: str,
        playbook_rule_id: str,
        original_text: str,
        proposed_redline: str,
        rationale: str,
    ) -> dict[str, Any]:
        """Stage a redline for mandatory human-in-the-loop legal sign-off."""
        approval_id = f"RED-{uuid.uuid4().hex[:8].upper()}"
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        risk = risk_level.upper()
        if risk not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
            risk = "HIGH"

        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO redline_approvals
                (approval_id, created_at, contract_id, counterparty, clause_title,
                 risk_level, playbook_rule_id, original_text, proposed_redline,
                 rationale, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING_APPROVAL')
                """,
                (
                    approval_id,
                    created_at,
                    contract_id,
                    counterparty,
                    clause_title,
                    risk,
                    playbook_rule_id,
                    original_text,
                    proposed_redline,
                    rationale,
                ),
            )
            conn.commit()
        finally:
            conn.close()

        return {
            "approval_id": approval_id,
            "status": "PENDING_APPROVAL",
            "risk_level": risk,
            "playbook_rule_id": playbook_rule_id,
            "message": (
                f"Staged redline {approval_id} for human Legal Counsel sign-off. "
                "AI agents cannot self-approve external contract redlines."
            ),
        }

    def list_approvals(self) -> list[dict[str, Any]]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM redline_approvals ORDER BY created_at DESC LIMIT 50"
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def decide_approval(
        self,
        approval_id: str,
        decision: str,
        caller_role: str,
        reviewer_note: str = "",
    ) -> dict[str, Any]:
        """Approve or reject a staged redline, enforcing strict RBAC."""
        if caller_role not in APPROVER_ROLES:
            raise RBACPermissionError(
                f"RBAC DENIED: Role '{caller_role}' cannot approve or reject legal redlines. "
                "Switch persona to 'Senior Legal Counsel' or 'General Counsel'."
            )

        normalized = decision.upper()
        if normalized not in {"APPROVED", "REJECTED"}:
            raise ValueError("Decision must be 'APPROVED' or 'REJECTED'.")

        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM redline_approvals WHERE approval_id = ?", (approval_id,)
            ).fetchone()
            if not row:
                raise KeyError(f"Approval ID '{approval_id}' not found.")

            # CRITICAL risks require General Counsel sign-off for approval.
            if normalized == "APPROVED" and row["risk_level"] == "CRITICAL" and caller_role != "general_counsel":
                raise RBACPermissionError(
                    f"RBAC DENIED: CRITICAL risk redline ({approval_id}) requires "
                    "'General Counsel / VP Legal' approval (Senior Legal Counsel cannot sign off)."
                )

            decided_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            conn.execute(
                """
                UPDATE redline_approvals
                SET status = ?, decided_by_role = ?, decided_at = ?, reviewer_note = ?
                WHERE approval_id = ?
                """,
                (normalized, caller_role, decided_at, reviewer_note, approval_id),
            )
            conn.commit()
            updated = conn.execute(
                "SELECT * FROM redline_approvals WHERE approval_id = ?", (approval_id,)
            ).fetchone()
            return dict(updated)
        finally:
            conn.close()
