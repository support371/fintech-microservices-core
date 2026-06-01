"""
Shared data models for the Nexus Compliance Agent System.
All agents share these canonical types to ensure consistency across
the ingestion → screening → audit → reporting pipeline.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class RiskScore(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DataStreamType(str, Enum):
    TRANSACTION_LOG = "transaction_log"
    USER_PROFILE = "user_profile"
    WATCHLIST_UPDATE = "watchlist_update"
    WEBHOOK_EVENT = "webhook_event"
    CARD_EVENT = "card_event"


class ScreeningRuleResult(str, Enum):
    PASS = "pass"
    FLAG = "flag"
    BLOCK = "block"


class AuditEventType(str, Enum):
    # Data ingestion
    DATA_INGESTED = "data_ingested"
    DATA_DEDUPLICATED = "data_deduplicated"
    WATCHLIST_VERSIONED = "watchlist_versioned"
    # Screening
    RULE_SCREENING_COMPLETE = "rule_screening_complete"
    LLM_ANALYSIS_COMPLETE = "llm_analysis_complete"
    RISK_SCORE_ASSIGNED = "risk_score_assigned"
    # Decisions
    TRANSACTION_APPROVED = "transaction_approved"
    TRANSACTION_FLAGGED = "transaction_flagged"
    TRANSACTION_BLOCKED = "transaction_blocked"
    # Human override
    HUMAN_OVERRIDE = "human_override"
    # SAR / Reporting
    SAR_GENERATED = "sar_generated"
    COMPLIANCE_REPORT_GENERATED = "compliance_report_generated"
    # System
    SYSTEM_EVENT = "system_event"


class OverrideAction(str, Enum):
    APPROVE = "approve"
    ESCALATE = "escalate"
    DISMISS = "dismiss"


# ---------------------------------------------------------------------------
# Core ingestion record
# ---------------------------------------------------------------------------

class IngestedRecord(BaseModel):
    """
    The canonical normalised form of any data stream record.
    Every record produced by the DataIngestionAgent MUST conform to this schema.
    """
    record_id: str = Field(
        default_factory=lambda: f"rec-{uuid.uuid4().hex[:12]}",
        description="Globally unique record ID assigned at ingestion time."
    )
    version_id: str = Field(
        description="Deterministic SHA-256 content hash used for deduplication."
    )
    ingested_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    stream_type: DataStreamType
    source: str = Field(description="Origin system/service label.")
    payload: Dict[str, Any] = Field(description="Normalised, sanitised payload.")
    raw_checksum: str = Field(description="SHA-256 of the raw bytes before normalisation.")
    is_duplicate: bool = False
    duplicate_of: Optional[str] = None   # record_id of the canonical original

    @field_validator("version_id", mode="before")
    @classmethod
    def _ensure_version_id(cls, v: str) -> str:
        return v or ""


class WatchlistVersion(BaseModel):
    """
    A versioned snapshot of a regulatory watchlist (e.g. OFAC SDN).
    Every screening decision records which watchlist_version_id was active.
    """
    watchlist_version_id: str = Field(
        default_factory=lambda: f"wl-{uuid.uuid4().hex[:12]}"
    )
    list_name: str                  # e.g. "OFAC_SDN", "EU_SANCTIONS"
    effective_date: datetime
    record_count: int
    checksum: str                   # SHA-256 of the raw list file
    source_url: Optional[str] = None
    loaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Screening models
# ---------------------------------------------------------------------------

class RuleCheckResult(BaseModel):
    rule_id: str
    rule_name: str
    result: ScreeningRuleResult
    detail: str
    triggered_value: Optional[Any] = None
    threshold: Optional[Any] = None


class LLMAnalysis(BaseModel):
    """Output produced by the LLM screening step."""
    model: str
    prompt_version: str
    risk_score: RiskScore
    confidence: float                       # 0.0 – 1.0
    flags: List[str]                        # e.g. ["structuring", "velocity_spike"]
    narrative: str                          # Plain-English explanation
    raw_response: str                       # Full LLM output stored for audit
    analysed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ScreeningResult(BaseModel):
    """
    Complete screening output for a single IngestedRecord.
    Combines rule-based results with the LLM analysis.
    """
    screening_id: str = Field(
        default_factory=lambda: f"scr-{uuid.uuid4().hex[:12]}"
    )
    record_id: str
    watchlist_version_id: str               # CRITICAL: traceability requirement
    screened_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    rule_results: List[RuleCheckResult]
    llm_analysis: Optional[LLMAnalysis] = None
    final_risk_score: RiskScore
    final_decision: ScreeningRuleResult     # Aggregated pass/flag/block
    decision_rationale: str


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------

class HumanOverride(BaseModel):
    """
    Mandatory structure for any human-initiated override of a system decision.
    The rationale field is required — empty string is rejected at the API layer.
    """
    override_id: str = Field(default_factory=lambda: f"ovr-{uuid.uuid4().hex[:12]}")
    actor_id: str
    actor_email: str
    action: OverrideAction
    rationale: str = Field(
        min_length=10,
        description="Required: minimum 10-character documented reason."
    )
    original_decision: ScreeningRuleResult
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditEntry(BaseModel):
    """
    A single immutable audit log entry.
    Once written, entries MUST NOT be modified or deleted.
    The `prev_entry_hash` forms a hash-chain for tamper detection.
    """
    entry_id: str = Field(
        default_factory=lambda: f"aud-{uuid.uuid4().hex[:12]}"
    )
    sequence_number: int                    # Monotonically increasing per-chain
    prev_entry_hash: str                    # SHA-256 of the previous entry's JSON
    event_type: AuditEventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_agent: str                       # Which agent produced this entry
    record_id: Optional[str] = None        # IngestedRecord this relates to
    screening_id: Optional[str] = None     # ScreeningResult this relates to
    watchlist_version_id: Optional[str] = None
    payload: Dict[str, Any]                # Full event context
    human_override: Optional[HumanOverride] = None
    entry_hash: Optional[str] = None       # SHA-256 of this entry's canonical JSON

    def compute_hash(self) -> str:
        """Deterministic hash of this entry excluding entry_hash itself."""
        import json
        data = self.model_dump(exclude={"entry_hash"})
        # Convert datetime objects to ISO strings for stable serialisation
        canonical = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()


# ---------------------------------------------------------------------------
# SAR / Reporting
# ---------------------------------------------------------------------------

class SARReport(BaseModel):
    """Suspicious Activity Report — pre-filled for regulatory submission."""
    sar_id: str = Field(default_factory=lambda: f"sar-{uuid.uuid4().hex[:12]}")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    generated_by_agent: str = "ReportingAgent"
    # Subject
    subject_user_id: str
    subject_name: Optional[str] = None
    subject_account: Optional[str] = None
    # Activity
    activity_start: datetime
    activity_end: datetime
    total_amount: float
    currency: str
    transaction_count: int
    # Flags
    risk_score: RiskScore
    flag_categories: List[str]
    # Narrative
    narrative: str
    supporting_audit_entry_ids: List[str]   # Links to AuditEntry.entry_id
    watchlist_version_ids_used: List[str]   # Full traceability
    # Submission status
    status: str = "draft"                   # draft | submitted | acknowledged
    filing_reference: Optional[str] = None


class ComplianceReport(BaseModel):
    """Periodic compliance summary report."""
    report_id: str = Field(default_factory=lambda: f"rpt-{uuid.uuid4().hex[:12]}")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    period_start: datetime
    period_end: datetime
    total_transactions: int
    approved_count: int
    flagged_count: int
    blocked_count: int
    sar_count: int
    human_override_count: int
    top_risk_categories: List[str]
    watchlist_versions_active: List[str]
    audit_chain_integrity: bool             # Result of hash-chain verification
    report_data: Dict[str, Any]             # Full breakdown
