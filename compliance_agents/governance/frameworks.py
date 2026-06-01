"""
Governance Framework Definitions
==================================
Encodes COBIT, COSO ERM, GAO AI Accountability, and IIA AI Auditing
as structured, machine-readable controls that map directly onto the
four Nexus compliance agents.

Design principle:
  Every control has a unique control_id, a mapped agent, a mapped
  AuditEventType, and a testable assertion function. This means:
  - Auditors can query the audit trail by control_id
  - The GovernanceEngine can run automated control-validation sweeps
  - Every AuditEntry gets tagged with the framework controls it satisfies

Frameworks and their primary focus areas for Nexus:
  COBIT 2019  — IT governance, data security, algorithmic bias prevention
  COSO ERM    — Enterprise risk strategy, AI-specific risk integration
  GAO AI      — Accountability standards, data integrity, explainability
  IIA AI      — Ethical AI, lifecycle oversight, independence of audit
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class Framework(str, Enum):
    COBIT   = "COBIT_2019"
    COSO    = "COSO_ERM"
    GAO     = "GAO_AI_ACCOUNTABILITY"
    IIA     = "IIA_AI_AUDITING"


class ControlCategory(str, Enum):
    # COBIT categories
    IT_GOVERNANCE        = "it_governance"
    DATA_SECURITY        = "data_security"
    BIAS_PREVENTION      = "algorithmic_bias_prevention"
    # COSO categories
    RISK_IDENTIFICATION  = "risk_identification"
    RISK_RESPONSE        = "risk_response"
    CONTROL_ACTIVITIES   = "control_activities"
    # GAO categories
    ACCOUNTABILITY       = "accountability"
    DATA_INTEGRITY       = "data_integrity"
    EXPLAINABILITY       = "explainability"
    TRANSPARENCY         = "transparency"
    # IIA categories
    ETHICAL_AI           = "ethical_ai"
    LIFECYCLE_OVERSIGHT  = "lifecycle_oversight"
    AUDIT_INDEPENDENCE   = "audit_independence"
    CONTINUOUS_MONITORING = "continuous_monitoring"


@dataclass
class GovernanceControl:
    """
    A single mappable governance control.
    Links a framework requirement to:
      - The Nexus agent responsible for satisfying it
      - The AuditEventType(s) that provide evidence of compliance
      - A testable assertion (callable) for automated sweep
    """
    control_id: str                         # e.g. "COBIT-DSS06.03"
    framework: Framework
    category: ControlCategory
    title: str
    description: str
    mapped_agent: str                       # e.g. "AuditTrailAgent"
    mapped_audit_events: List[str]          # AuditEventType values
    implementation_notes: str
    assertion: Optional[Callable[[Dict[str, Any]], bool]] = field(
        default=None, repr=False
    )
    evidence_fields: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# COBIT 2019 Controls
# Focus: IT governance, data security, algorithmic bias management
# ---------------------------------------------------------------------------

COBIT_CONTROLS: List[GovernanceControl] = [

    GovernanceControl(
        control_id="COBIT-APO12.01",
        framework=Framework.COBIT,
        category=ControlCategory.RISK_IDENTIFICATION,
        title="Collect Data on AI/Algorithmic Risk",
        description=(
            "Establish and maintain a process to identify, classify, and "
            "catalogue risks associated with algorithmic decision-making, "
            "including bias, explainability gaps, and data quality failures."
        ),
        mapped_agent="DataIngestionAgent",
        mapped_audit_events=["data_ingested", "watchlist_versioned"],
        implementation_notes=(
            "DataIngestionAgent normalises all input streams and assigns "
            "content-addressed version_ids. Every record type (transaction_log, "
            "user_profile, watchlist_update) is catalogued with source and timestamp. "
            "Bias risk is managed by ensuring watchlist versions are dated and "
            "traceable — preventing stale lists from silently affecting decisions."
        ),
        evidence_fields=["version_id", "stream_type", "source", "raw_checksum"],
    ),

    GovernanceControl(
        control_id="COBIT-DSS06.03",
        framework=Framework.COBIT,
        category=ControlCategory.DATA_SECURITY,
        title="Manage Data Security and Integrity",
        description=(
            "Ensure that data used in automated decisions is protected against "
            "unauthorised modification, tampering, or deletion. Verify integrity "
            "continuously and flag any detected anomalies."
        ),
        mapped_agent="AuditTrailAgent",
        mapped_audit_events=["system_event"],
        implementation_notes=(
            "The audit_log table is protected by SQLite BEFORE UPDATE / BEFORE DELETE "
            "triggers that ABORT any mutation attempt. Additionally, a SHA-256 hash-chain "
            "links every entry — verify_chain_integrity() detects any tampering, gap, "
            "or reordering at the database level. COBIT DSS06.03 is satisfied by "
            "running verify_chain_integrity() on a scheduled basis and recording "
            "the result in a system_event audit entry."
        ),
        evidence_fields=["entry_hash", "prev_entry_hash", "sequence_number"],
    ),

    GovernanceControl(
        control_id="COBIT-DSS06.06",
        framework=Framework.COBIT,
        category=ControlCategory.BIAS_PREVENTION,
        title="Manage Algorithmic Bias in Automated Decisions",
        description=(
            "Ensure that automated screening models (rule-based and AI/ML) are "
            "periodically reviewed for discriminatory patterns. Maintain an audit "
            "trail of every model version and decision rationale to enable bias "
            "analysis by protected class."
        ),
        mapped_agent="ScreeningAgent",
        mapped_audit_events=["transaction_approved", "transaction_flagged", "transaction_blocked", "llm_analysis_complete"],
        implementation_notes=(
            "Every ScreeningResult stores: the LLM model version, prompt_version, "
            "confidence score, and the raw LLM response verbatim. The watchlist_version_id "
            "ensures decisions are traceable to the exact list active at screening time. "
            "Bias analysis: query audit_log for transaction_blocked events, cross-reference "
            "user_profile stream data, and compute block-rate distributions by geography, "
            "KYC tier, and currency. The GovernanceEngine.bias_analysis() method "
            "automates this sweep."
        ),
        evidence_fields=["llm_analysis.model", "llm_analysis.prompt_version", "watchlist_version_id", "decision_rationale"],
    ),

    GovernanceControl(
        control_id="COBIT-MEA01.03",
        framework=Framework.COBIT,
        category=ControlCategory.IT_GOVERNANCE,
        title="Monitor AI System Performance and Control Effectiveness",
        description=(
            "Establish KPIs for the compliance AI system. Track decision accuracy, "
            "false positive rates, override frequency, and rule trigger distributions. "
            "Report to governance on a defined cadence."
        ),
        mapped_agent="ReportingAgent",
        mapped_audit_events=["compliance_report_generated", "sar_generated"],
        implementation_notes=(
            "The ReportingAgent.generate_compliance_report() produces a structured "
            "report including: approved/flagged/blocked counts, SAR count, human "
            "override frequency, top risk flag categories, and chain integrity status. "
            "This report is itself recorded as an audit entry. "
            "COBIT MEA01.03 KPIs: override_rate = human_overrides / total_decisions, "
            "flag_rate = flagged / total, sar_rate = sars / flagged."
        ),
        evidence_fields=["report_data.decisions", "report_data.human_overrides", "audit_chain_integrity"],
    ),
]


# ---------------------------------------------------------------------------
# COSO ERM Controls
# Focus: AI-specific enterprise risk integration across all risk categories
# ---------------------------------------------------------------------------

COSO_CONTROLS: List[GovernanceControl] = [

    GovernanceControl(
        control_id="COSO-GOV.02",
        framework=Framework.COSO,
        category=ControlCategory.RISK_IDENTIFICATION,
        title="Integrate AI Risk into Enterprise Risk Taxonomy",
        description=(
            "Classify AI-related risks (model risk, data risk, bias risk, "
            "explainability risk) within the enterprise risk register. Each AI "
            "risk must map to at least one compensating control."
        ),
        mapped_agent="NexusComplianceOrchestrator",
        mapped_audit_events=["data_ingested", "risk_score_assigned", "transaction_blocked"],
        implementation_notes=(
            "The Nexus system addresses four COSO AI risk categories: "
            "(1) Model risk → ScreeningAgent LLM version tracking and rule registry. "
            "(2) Data risk → DataIngestionAgent deduplication and versioning. "
            "(3) Bias risk → GovernanceEngine bias_analysis() sweep (COBIT-DSS06.06). "
            "(4) Explainability risk → Every decision stores decision_rationale and "
            "full LLM raw_response. The GovernanceEngine.coso_risk_register() method "
            "produces a structured risk register consumable by ERM tools."
        ),
        evidence_fields=["final_risk_score", "decision_rationale", "llm_analysis.narrative"],
    ),

    GovernanceControl(
        control_id="COSO-RC.05",
        framework=Framework.COSO,
        category=ControlCategory.RISK_RESPONSE,
        title="Define and Execute AI Risk Response Actions",
        description=(
            "For each identified AI risk, define a response: accept, mitigate, "
            "transfer, or avoid. Automated blocking and flagging are risk mitigation "
            "responses. Human overrides must be documented as risk acceptance decisions."
        ),
        mapped_agent="ScreeningAgent",
        mapped_audit_events=["transaction_flagged", "transaction_blocked", "human_override"],
        implementation_notes=(
            "The three screening decisions map directly to COSO risk responses: "
            "PASS → risk accepted (within appetite). "
            "FLAG → risk mitigated (human review required). "
            "BLOCK → risk avoided (transaction halted). "
            "Human override → documented risk acceptance. The override rationale "
            "(min 10 chars, stored permanently) is the COSO-required documentation "
            "of the risk acceptance decision. The GovernanceEngine surfaces overrides "
            "tagged with COSO-RC.05 for ERM reporting."
        ),
        evidence_fields=["final_decision", "human_override.rationale", "human_override.action"],
    ),

    GovernanceControl(
        control_id="COSO-CA.03",
        framework=Framework.COSO,
        category=ControlCategory.CONTROL_ACTIVITIES,
        title="Deploy Control Activities Over AI Processing",
        description=(
            "Implement specific control activities over AI data inputs, model "
            "processing, and outputs. Controls must be preventive (rules), "
            "detective (LLM flags), and corrective (human overrides)."
        ),
        mapped_agent="ScreeningAgent",
        mapped_audit_events=["rule_screening_complete", "llm_analysis_complete", "human_override"],
        implementation_notes=(
            "The three-layer control structure directly satisfies COSO CA.03: "
            "Preventive → 7 rule-based checks (geographic block, KYC, AML limits). "
            "Detective → Claude LLM analysis identifies patterns rules miss. "
            "Corrective → Human override workflow with mandatory documented rationale. "
            "All three layers are independently recorded in the audit trail, giving "
            "auditors a complete control activity log per transaction."
        ),
        evidence_fields=["rule_results", "llm_analysis.flags", "human_override"],
    ),

    GovernanceControl(
        control_id="COSO-INFO.04",
        framework=Framework.COSO,
        category=ControlCategory.CONTROL_ACTIVITIES,
        title="Use Relevant, Quality Information for AI Decisions",
        description=(
            "Ensure that the information used by the AI system is accurate, "
            "timely, and version-controlled. Stale or corrupted data must not "
            "silently influence automated decisions."
        ),
        mapped_agent="DataIngestionAgent",
        mapped_audit_events=["data_ingested", "watchlist_versioned"],
        implementation_notes=(
            "DataIngestionAgent enforces information quality at three points: "
            "(1) Normalisation — nulls stripped, currencies uppercased, amounts coerced. "
            "(2) Content-addressed versioning — version_id is SHA-256 of normalised "
            "payload, making data drift detectable. "
            "(3) Watchlist version tracking — every screening references a specific "
            "watchlist_version_id with an effective_date and checksum, preventing "
            "stale sanctions lists from silently affecting decisions."
        ),
        evidence_fields=["version_id", "raw_checksum", "watchlist_version_id", "effective_date"],
    ),
]


# ---------------------------------------------------------------------------
# GAO AI Accountability Framework Controls
# Focus: Accountability, data integrity, explainability for auditors
# ---------------------------------------------------------------------------

GAO_CONTROLS: List[GovernanceControl] = [

    GovernanceControl(
        control_id="GAO-AI-ACC.01",
        framework=Framework.GAO,
        category=ControlCategory.ACCOUNTABILITY,
        title="Establish Clear Lines of Accountability for AI Decisions",
        description=(
            "Every automated AI decision must have a clearly identified accountable "
            "party. Automated decisions require documented rationale. Human overrides "
            "require identified actors with documented justification."
        ),
        mapped_agent="AuditTrailAgent",
        mapped_audit_events=["transaction_approved", "transaction_flagged", "transaction_blocked", "human_override"],
        implementation_notes=(
            "Accountability is enforced at two levels: "
            "Automated decisions: source_agent field identifies the producing agent, "
            "decision_rationale documents the combined rule + LLM reasoning, and "
            "watchlist_version_id creates traceability to the data source. "
            "Human decisions: human_override.actor_id and actor_email identify the "
            "person. rationale (min 10 chars) documents the justification. "
            "override_id creates a permanent reference. All are immutable once written."
        ),
        evidence_fields=["source_agent", "decision_rationale", "human_override.actor_email", "human_override.rationale"],
    ),

    GovernanceControl(
        control_id="GAO-AI-DI.02",
        framework=Framework.GAO,
        category=ControlCategory.DATA_INTEGRITY,
        title="Verify and Maintain AI Training and Input Data Integrity",
        description=(
            "Establish mechanisms to verify that data inputs to AI systems have "
            "not been corrupted or tampered with. Maintain version history of all "
            "data sources used in decision-making."
        ),
        mapped_agent="DataIngestionAgent",
        mapped_audit_events=["data_ingested", "watchlist_versioned"],
        implementation_notes=(
            "GAO DI.02 is satisfied by three mechanisms: "
            "(1) raw_checksum — SHA-256 of the raw bytes before normalisation, "
            "enabling detection of in-transit corruption. "
            "(2) version_id — SHA-256 of the normalised payload, enabling detection "
            "of post-normalisation drift. "
            "(3) Watchlist checksum — SHA-256 of the raw watchlist file, with "
            "effective_date and source_url recorded, providing full data lineage."
        ),
        evidence_fields=["raw_checksum", "version_id", "watchlist_versions.checksum", "watchlist_versions.source_url"],
    ),

    GovernanceControl(
        control_id="GAO-AI-EX.03",
        framework=Framework.GAO,
        category=ControlCategory.EXPLAINABILITY,
        title="Ensure AI Decisions are Explainable to Oversight Bodies",
        description=(
            "Automated AI decisions must be explainable at a level of detail "
            "sufficient for regulators, auditors, and affected parties to "
            "understand why a decision was made."
        ),
        mapped_agent="ScreeningAgent",
        mapped_audit_events=["transaction_flagged", "transaction_blocked", "llm_analysis_complete"],
        implementation_notes=(
            "Explainability is provided at three granularities: "
            "(1) Rule level: each triggered rule includes rule_id, rule_name, "
            "triggered_value, threshold, and a plain-English detail string. "
            "(2) LLM level: the full Claude narrative is stored verbatim, plus "
            "structured flags (e.g. 'structuring', 'velocity_spike'). "
            "(3) Summary level: decision_rationale combines both into a single "
            "auditor-readable explanation. The ReportingAgent surfaces this "
            "in SARs under the 'narrative' field."
        ),
        evidence_fields=["rule_results[].detail", "llm_analysis.narrative", "llm_analysis.flags", "decision_rationale"],
    ),

    GovernanceControl(
        control_id="GAO-AI-TR.04",
        framework=Framework.GAO,
        category=ControlCategory.TRANSPARENCY,
        title="Maintain Transparency in AI Model Use and Versioning",
        description=(
            "Document which AI models, versions, and configurations were used "
            "in each decision. Regulators must be able to reconstruct the exact "
            "state of the AI system at any historical decision point."
        ),
        mapped_agent="ScreeningAgent",
        mapped_audit_events=["llm_analysis_complete", "risk_score_assigned"],
        implementation_notes=(
            "Model transparency is enforced via LLMAnalysis fields: "
            "model (e.g. 'claude-opus-4-5'), prompt_version (e.g. 'v1.2.0'), "
            "and raw_response (verbatim output). Combined with watchlist_version_id, "
            "analysts can reconstruct the exact AI state at any historical decision: "
            "which model, which prompt version, which sanctions list, and what the "
            "raw output was. The GovernanceEngine.reconstruct_decision() method "
            "assembles this full picture from a single screening_id."
        ),
        evidence_fields=["llm_analysis.model", "llm_analysis.prompt_version", "llm_analysis.raw_response", "watchlist_version_id"],
    ),
]


# ---------------------------------------------------------------------------
# IIA AI Auditing Framework Controls
# Focus: Ethical AI, lifecycle oversight, internal audit independence
# ---------------------------------------------------------------------------

IIA_CONTROLS: List[GovernanceControl] = [

    GovernanceControl(
        control_id="IIA-AI-ETH.01",
        framework=Framework.IIA,
        category=ControlCategory.ETHICAL_AI,
        title="Embed Ethical Principles in AI Decision Processes",
        description=(
            "Ensure AI systems operate within defined ethical boundaries: "
            "fairness (no discriminatory outcomes), accountability (every "
            "decision has an owner), transparency (decisions are explainable), "
            "and privacy (personal data is protected)."
        ),
        mapped_agent="ScreeningAgent",
        mapped_audit_events=["transaction_approved", "transaction_flagged", "transaction_blocked"],
        implementation_notes=(
            "Ethical AI is embedded structurally: "
            "Fairness → 7 rule checks apply uniformly; LLM bias_analysis() sweeps "
            "block-rate distributions. Rules are transparent and listed in rules.py. "
            "Accountability → Every decision has source_agent + decision_rationale. "
            "Transparency → Full rule results and LLM narrative stored per decision. "
            "Privacy → Payloads stored in the compliance DB, not in log files. "
            "The IIA ETH.01 assertion runs the GovernanceEngine.ethical_ai_sweep() "
            "which checks fairness metrics and flags anomalous block-rate patterns."
        ),
        evidence_fields=["source_agent", "rule_results", "llm_analysis.narrative", "decision_rationale"],
    ),

    GovernanceControl(
        control_id="IIA-AI-LC.02",
        framework=Framework.IIA,
        category=ControlCategory.LIFECYCLE_OVERSIGHT,
        title="Oversee the Full AI System Lifecycle",
        description=(
            "Internal audit must have visibility over the entire AI lifecycle: "
            "model selection, deployment, ongoing monitoring, and retirement. "
            "Changes to models or rules must be logged and reviewed."
        ),
        mapped_agent="AuditTrailAgent",
        mapped_audit_events=["system_event", "compliance_report_generated"],
        implementation_notes=(
            "Lifecycle oversight is implemented via: "
            "(1) LLM model + prompt_version tracked per-decision in LLMAnalysis. "
            "(2) Rule registry is versioned in rules.py — changes require a code "
            "commit and build gate via the nexus-locked-build workflow. "
            "(3) system_event audit entries are emitted for watchlist updates, "
            "service restarts, and configuration changes. "
            "(4) Compliance reports include the active watchlist versions and "
            "chain integrity status, giving audit a periodic lifecycle snapshot."
        ),
        evidence_fields=["llm_analysis.model", "llm_analysis.prompt_version", "watchlist_version_id", "loaded_at"],
    ),

    GovernanceControl(
        control_id="IIA-AI-IND.03",
        framework=Framework.IIA,
        category=ControlCategory.AUDIT_INDEPENDENCE,
        title="Maintain Independence of the Internal Audit Function",
        description=(
            "The audit trail and reporting mechanisms must be independent of "
            "the operational systems they audit. Audit data must not be modifiable "
            "by operational staff. Read-only auditor access must be enforced."
        ),
        mapped_agent="AuditTrailAgent",
        mapped_audit_events=["system_event"],
        implementation_notes=(
            "Audit independence is enforced at three levels: "
            "(1) The audit_log table has DB-level ABORT triggers on UPDATE/DELETE — "
            "operational staff cannot alter entries even with DB access. "
            "(2) The AuditTrailAgent exposes only query() and verify_chain_integrity() "
            "to external callers — no mutation methods are public. "
            "(3) The hash-chain provides an independent verification mechanism: "
            "auditors can verify integrity without trusting the application layer. "
            "Future: the audit DB should be on a separate RDS instance with "
            "read-only credentials for operational services."
        ),
        evidence_fields=["entry_hash", "prev_entry_hash", "sequence_number"],
    ),

    GovernanceControl(
        control_id="IIA-AI-CM.04",
        framework=Framework.IIA,
        category=ControlCategory.CONTINUOUS_MONITORING,
        title="Implement Continuous Monitoring of AI System Outputs",
        description=(
            "Internal audit must continuously monitor AI outputs for drift, "
            "unexpected patterns, and control failures. Monitoring results must "
            "be reported on a defined cadence with documented findings."
        ),
        mapped_agent="ReportingAgent",
        mapped_audit_events=["compliance_report_generated", "sar_generated"],
        implementation_notes=(
            "Continuous monitoring is implemented via: "
            "(1) ReportingAgent.generate_compliance_report() — runs on a configurable "
            "cadence (default: every 24h), produces decision distributions and "
            "chain integrity verification. "
            "(2) Auto-SAR trigger — any HIGH/CRITICAL screening result immediately "
            "generates a draft SAR, ensuring no high-risk event goes unaddressed. "
            "(3) GovernanceEngine.run_full_sweep() — executes all control assertions "
            "across all four frameworks and produces a governance_report.json. "
            "The IIA CM.04 assertion checks: override_rate < 5%, flag_rate stable "
            "within ±10% week-over-week, chain integrity == True."
        ),
        evidence_fields=["report_data.decisions", "audit_chain_integrity", "sar_count", "human_override_count"],
    ),
]


# ---------------------------------------------------------------------------
# Master control registry
# ---------------------------------------------------------------------------

ALL_CONTROLS: List[GovernanceControl] = (
    COBIT_CONTROLS + COSO_CONTROLS + GAO_CONTROLS + IIA_CONTROLS
)

CONTROL_MAP: Dict[str, GovernanceControl] = {
    ctrl.control_id: ctrl for ctrl in ALL_CONTROLS
}


def get_controls_for_agent(agent_name: str) -> List[GovernanceControl]:
    return [c for c in ALL_CONTROLS if c.mapped_agent == agent_name]


def get_controls_for_framework(framework: Framework) -> List[GovernanceControl]:
    return [c for c in ALL_CONTROLS if c.framework == framework]


def get_controls_for_event(event_type: str) -> List[GovernanceControl]:
    return [c for c in ALL_CONTROLS if event_type in c.mapped_audit_events]
