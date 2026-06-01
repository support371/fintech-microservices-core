"""
Nexus Compliance Service — FastAPI Application
===============================================
Exposes all four compliance agents as a REST API.

Endpoints:
  POST /compliance/ingest              — Ingest a data stream record
  POST /compliance/screen              — Ingest + screen in one call
  POST /compliance/watchlist/upload    — Upload a new watchlist version
  POST /compliance/override            — Apply a human override
  GET  /compliance/audit               — Query the audit trail
  GET  /compliance/audit/integrity     — Verify hash-chain integrity
  POST /compliance/report/sar          — Generate a SAR
  GET  /compliance/report/compliance   — Generate a compliance report
  GET  /compliance/health              — Health check

Integration with existing services:
  The existing card_platform_service and converter_service can POST to
  /compliance/screen instead of their local compliance checks. The
  orchestrator handles ingestion, screening, and audit trail automatically.

Authentication:
  Uses the same HMAC-based pattern as the existing converter_service.
  Internal calls from card_platform_service use the COMPLIANCE_INTERNAL_SECRET.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from compliance_agents.orchestrator import NexusComplianceOrchestrator
from compliance_agents.shared.models import DataStreamType, OverrideAction

logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp":"%(asctime)s","service":"compliance","level":"%(levelname)s","message":"%(message)s"}'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Nexus Compliance Service",
    description="Four-agent compliance system: Data Ingestion, Screening (Rules + LLM), Audit Trail, Reporting.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Singleton orchestrator
_orchestrator: Optional[NexusComplianceOrchestrator] = None


def get_orchestrator() -> NexusComplianceOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = NexusComplianceOrchestrator()
    return _orchestrator


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class IngestRequest(BaseModel):
    stream_type: str = Field(default="transaction_log", description="One of: transaction_log, user_profile, watchlist_update, webhook_event, card_event")
    source: str = Field(description="Origin service label, e.g. 'converter_service'")
    payload: Dict[str, Any]


class ScreenRequest(BaseModel):
    stream_type: str = "transaction_log"
    source: str
    payload: Dict[str, Any]
    watchlist_entries: Optional[List[str]] = None
    force_llm: bool = False


class WatchlistUploadRequest(BaseModel):
    list_name: str = Field(description="e.g. 'OFAC_SDN', 'EU_SANCTIONS'")
    raw_content_hex: str = Field(description="Hex-encoded raw list content (SHA-256 checksummed)")
    record_count: int
    effective_date: str = Field(description="ISO 8601 date, e.g. '2026-06-01'")
    source_url: Optional[str] = None


class HumanOverrideRequest(BaseModel):
    screening_id: str
    actor_id: str
    actor_email: str
    action: str = Field(description="One of: approve, escalate, dismiss")
    rationale: str = Field(
        min_length=10,
        description="REQUIRED: Document the specific reason for this override (min 10 chars)."
    )


class SARRequest(BaseModel):
    subject_user_id: str
    hours_back: int = Field(default=72, ge=1, le=8760)
    override_narrative: Optional[str] = None


class AuditQueryParams(BaseModel):
    event_type: Optional[str] = None
    record_id: Optional[str] = None
    screening_id: Optional[str] = None
    watchlist_version_id: Optional[str] = None
    from_dt: Optional[str] = None
    to_dt: Optional[str] = None
    human_overrides_only: bool = False
    limit: int = Field(default=50, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/compliance/health")
def health():
    return {"status": "healthy", "service": "compliance-service", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.post("/compliance/ingest")
def ingest_record(req: IngestRequest):
    """Ingest a raw data record — normalise, deduplicate, version, and persist."""
    try:
        orch = get_orchestrator()
        record = orch._ingestion.ingest(
            stream_type=req.stream_type,
            source=req.source,
            raw=req.payload,
        )
        audit_entry = orch._audit.record_ingestion(record)
        return {
            "record_id":        record.record_id,
            "version_id":       record.version_id,
            "is_duplicate":     record.is_duplicate,
            "duplicate_of":     record.duplicate_of,
            "audit_entry_id":   audit_entry.entry_id,
            "ingested_at":      record.ingested_at.isoformat(),
        }
    except Exception as exc:
        logger.error(f"[API] Ingest failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/compliance/screen")
def screen_transaction(req: ScreenRequest):
    """
    Full pipeline: ingest → screen (rules + LLM) → audit.
    Returns the complete screening result including risk score and decision.
    This is the primary endpoint for card_platform_service and converter_service.
    """
    try:
        orch = get_orchestrator()
        result = orch.process_transaction(
            raw_payload=req.payload,
            source=req.source,
            stream_type=req.stream_type,
            watchlist_entries=req.watchlist_entries,
            force_llm=req.force_llm,
        )
        return result
    except Exception as exc:
        logger.error(f"[API] Screening failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/compliance/watchlist/upload")
def upload_watchlist(req: WatchlistUploadRequest):
    """Version a new regulatory watchlist. Returns the new watchlist_version_id."""
    try:
        orch = get_orchestrator()
        raw_content = bytes.fromhex(req.raw_content_hex)
        effective_date = datetime.fromisoformat(req.effective_date).replace(tzinfo=timezone.utc)
        wl = orch.process_watchlist_update(
            list_name=req.list_name,
            raw_content=raw_content,
            record_count=req.record_count,
            effective_date=effective_date,
            source_url=req.source_url,
        )
        return {
            "watchlist_version_id": wl.watchlist_version_id,
            "list_name":    wl.list_name,
            "record_count": wl.record_count,
            "checksum":     wl.checksum,
            "effective_date": wl.effective_date.isoformat(),
            "loaded_at":    wl.loaded_at.isoformat(),
        }
    except Exception as exc:
        logger.error(f"[API] Watchlist upload failed: {exc}")
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/compliance/override")
def apply_human_override(req: HumanOverrideRequest):
    """
    Record a human analyst override of a system screening decision.
    Rationale is MANDATORY and permanently stored in the audit trail.
    """
    try:
        orch = get_orchestrator()
        entry = orch.apply_human_override(
            screening_id=req.screening_id,
            actor_id=req.actor_id,
            actor_email=req.actor_email,
            action=req.action,
            rationale=req.rationale,
        )
        return {
            "status":           "override_recorded",
            "audit_entry_id":   entry.entry_id,
            "sequence_number":  entry.sequence_number,
            "override_action":  req.action,
            "actor":            req.actor_email,
            "timestamp":        entry.timestamp.isoformat(),
            "message":          "Override permanently recorded in immutable audit trail.",
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error(f"[API] Override failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/compliance/audit/query")
def query_audit(params: AuditQueryParams):
    """
    Query the immutable audit trail with rich filtering.
    Designed for auditor access and compliance review dashboards.
    """
    try:
        orch = get_orchestrator()
        from_dt = datetime.fromisoformat(params.from_dt) if params.from_dt else None
        to_dt = datetime.fromisoformat(params.to_dt) if params.to_dt else None

        entries = orch.query_audit_trail(
            event_type=params.event_type,
            record_id=params.record_id,
            screening_id=params.screening_id,
            watchlist_version_id=params.watchlist_version_id,
            from_dt=from_dt,
            to_dt=to_dt,
            human_overrides_only=params.human_overrides_only,
            limit=params.limit,
            offset=params.offset,
        )

        return {
            "count": len(entries),
            "entries": [
                {
                    "entry_id":              e.entry_id,
                    "sequence_number":       e.sequence_number,
                    "event_type":            e.event_type.value,
                    "timestamp":             e.timestamp.isoformat(),
                    "source_agent":          e.source_agent,
                    "record_id":             e.record_id,
                    "screening_id":          e.screening_id,
                    "watchlist_version_id":  e.watchlist_version_id,
                    "payload":               e.payload,
                    "human_override":        e.human_override.model_dump() if e.human_override else None,
                    "entry_hash":            e.entry_hash,
                    "prev_entry_hash":       e.prev_entry_hash,
                }
                for e in entries
            ],
        }
    except Exception as exc:
        logger.error(f"[API] Audit query failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/compliance/audit/integrity")
def verify_audit_integrity():
    """
    Verify the cryptographic hash-chain integrity of the entire audit log.
    Any tampering, deletion, or modification will be detected here.
    """
    try:
        orch = get_orchestrator()
        result = orch.verify_audit_integrity()
        status_code = 200 if result.get("integrity_ok") else 409
        return result
    except Exception as exc:
        logger.error(f"[API] Integrity check failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/compliance/report/sar")
def generate_sar(req: SARRequest):
    """Generate a Suspicious Activity Report for a user."""
    try:
        orch = get_orchestrator()
        to_dt = datetime.now(timezone.utc)
        from_dt = to_dt - __import__("datetime").timedelta(hours=req.hours_back)

        sar = orch._reporting.generate_sar(
            subject_user_id=req.subject_user_id,
            from_dt=from_dt,
            to_dt=to_dt,
            override_narrative=req.override_narrative,
        )
        return {
            "sar_id":               sar.sar_id,
            "status":               sar.status,
            "subject_user_id":      sar.subject_user_id,
            "risk_score":           sar.risk_score.value,
            "total_amount":         sar.total_amount,
            "currency":             sar.currency,
            "transaction_count":    sar.transaction_count,
            "flag_categories":      sar.flag_categories,
            "narrative":            sar.narrative,
            "watchlist_versions":   sar.watchlist_version_ids_used,
            "supporting_entries":   sar.supporting_audit_entry_ids,
            "generated_at":         sar.generated_at.isoformat(),
        }
    except Exception as exc:
        logger.error(f"[API] SAR generation failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/compliance/report/compliance")
def generate_compliance_report(period_hours: int = 24):
    """Generate a periodic compliance summary report."""
    try:
        orch = get_orchestrator()
        report = orch.generate_compliance_report(period_hours=period_hours)
        return {
            "report_id":                report.report_id,
            "period_start":             report.period_start.isoformat(),
            "period_end":               report.period_end.isoformat(),
            "total_transactions":       report.total_transactions,
            "approved_count":           report.approved_count,
            "flagged_count":            report.flagged_count,
            "blocked_count":            report.blocked_count,
            "sar_count":                report.sar_count,
            "human_override_count":     report.human_override_count,
            "top_risk_categories":      report.top_risk_categories,
            "watchlist_versions_active": report.watchlist_versions_active,
            "audit_chain_integrity":    report.audit_chain_integrity,
            "report_data":              report.report_data,
            "generated_at":             report.generated_at.isoformat(),
        }
    except Exception as exc:
        logger.error(f"[API] Compliance report failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


# ---------------------------------------------------------------------------
# Governance Framework Routes (COBIT / COSO ERM / GAO / IIA)
# ---------------------------------------------------------------------------

from compliance_agents.governance.engine import GovernanceEngine
from compliance_agents.governance.frameworks import Framework

_governance_engine: Optional[GovernanceEngine] = None

def get_governance_engine() -> GovernanceEngine:
    global _governance_engine
    if _governance_engine is None:
        _governance_engine = GovernanceEngine()
    return _governance_engine


@app.get("/compliance/governance/sweep")
def governance_full_sweep(period_hours: int = 24):
    """
    Run a full cross-framework governance sweep across all four frameworks:
    COBIT 2019, COSO ERM, GAO AI Accountability, IIA AI Auditing.
    Returns per-framework control status + bias analysis + chain integrity.
    """
    try:
        engine = get_governance_engine()
        report = engine.run_full_sweep(period_hours=period_hours)
        return report.to_dict()
    except Exception as exc:
        logger.error(f"[API] Governance sweep failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/compliance/governance/framework/{framework_id}")
def assess_framework(framework_id: str, period_hours: int = 24):
    """
    Assess a single governance framework.
    framework_id: COBIT_2019 | COSO_ERM | GAO_AI_ACCOUNTABILITY | IIA_AI_AUDITING
    """
    try:
        fw = Framework(framework_id)
        engine = get_governance_engine()
        report = engine.assess_framework(fw, period_hours=period_hours)
        return report.to_dict()
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown framework: {framework_id}. Valid: {[f.value for f in Framework]}")
    except Exception as exc:
        logger.error(f"[API] Framework assessment failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/compliance/governance/controls")
def list_controls(framework: Optional[str] = None, agent: Optional[str] = None):
    """List all governance controls, optionally filtered by framework or agent."""
    try:
        engine = get_governance_engine()
        return {"controls": engine.list_controls(framework=framework, agent=agent)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/compliance/governance/controls/{control_id}")
def get_control(control_id: str):
    """Get the full definition and implementation notes for a specific control."""
    engine = get_governance_engine()
    ctrl = engine.get_control(control_id)
    if not ctrl:
        raise HTTPException(status_code=404, detail=f"Control {control_id} not found.")
    return ctrl


@app.get("/compliance/governance/reconstruct/{screening_id}")
def reconstruct_decision(screening_id: str):
    """
    GAO-AI-TR.04: Reconstruct the full AI system state at the time of a
    specific screening decision — model version, prompt, watchlist, rules,
    LLM output, and any human overrides. Essential for regulator enquiries.
    """
    try:
        engine = get_governance_engine()
        return engine.reconstruct_decision(screening_id)
    except Exception as exc:
        logger.error(f"[API] Decision reconstruction failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/compliance/governance/bias")
def bias_analysis(period_hours: int = 168):
    """
    COBIT-DSS06.06 / IIA-AI-ETH.01: Analyse block-rate distributions by
    geography, KYC tier, and currency to surface algorithmic bias patterns.
    Default window: 7 days (168 hours).
    """
    try:
        engine = get_governance_engine()
        return engine.run_bias_analysis(period_hours=period_hours)
    except Exception as exc:
        logger.error(f"[API] Bias analysis failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
