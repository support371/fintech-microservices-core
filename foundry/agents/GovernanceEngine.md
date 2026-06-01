# GovernanceEngine

## Purpose

The Governance Engine is the cross-framework oversight layer that maps
COBIT 2019, COSO ERM, GAO AI Accountability, and IIA AI Auditing controls
onto the Nexus compliance agent system. It provides automated control
assertions, bias analysis, decision reconstruction, and a unified governance
sweep report for board, audit committee, and regulatory consumption.

## The Four Frameworks and Their Role in Nexus

### COBIT 2019 — IT Governance & Data Security
Addresses the hardest technical questions auditors ask about algorithmic systems:
- Is the data ironclad? (content-addressed versioning, raw checksums)
- Can the system bias against protected groups? (bias_analysis() sweep)
- Is the AI being monitored as a governance asset? (MEA01.03 KPIs)
- Is the audit data tamper-proof? (hash-chain, DB triggers)

### COSO ERM — Enterprise Risk Integration
Integrates AI risk directly into the enterprise risk management taxonomy:
- AI risk classification (model, data, bias, explainability) → COSO-GOV.02
- Decision → risk response mapping: PASS=accept, FLAG=mitigate, BLOCK=avoid
- Human overrides = documented risk acceptance decisions → COSO-RC.05
- Three-layer control structure (preventive + detective + corrective) → COSO-CA.03

### GAO AI Accountability Framework — Accountability & Explainability
Specifically designed for regulatory accountability and auditor access:
- Every decision has an identified accountable agent → GAO-AI-ACC.01
- Full data lineage with checksums and version history → GAO-AI-DI.02
- Three-level explainability: rule-level, LLM narrative, summary → GAO-AI-EX.03
- Full AI state reconstruction per decision → GAO-AI-TR.04

### IIA AI Auditing Framework — Ethical AI & Lifecycle Oversight
Addresses internal audit's requirements for independence and ethics:
- Fairness analysis and structured ethical principles → IIA-AI-ETH.01
- AI lifecycle visibility (model version, rule versions, watchlist) → IIA-AI-LC.02
- Audit independence via DB triggers and public-only read methods → IIA-AI-IND.03
- Continuous monitoring with override rate thresholds → IIA-AI-CM.04

## Controls Summary (16 total)

| Control ID         | Framework | Title                                          | Agent                    |
|--------------------|-----------|------------------------------------------------|--------------------------|
| COBIT-APO12.01     | COBIT     | Collect Data on AI/Algorithmic Risk            | DataIngestionAgent       |
| COBIT-DSS06.03     | COBIT     | Manage Data Security and Integrity             | AuditTrailAgent          |
| COBIT-DSS06.06     | COBIT     | Manage Algorithmic Bias in Automated Decisions | ScreeningAgent           |
| COBIT-MEA01.03     | COBIT     | Monitor AI System Performance                  | ReportingAgent           |
| COSO-GOV.02        | COSO ERM  | Integrate AI Risk into Enterprise Risk Taxonomy| Orchestrator             |
| COSO-RC.05         | COSO ERM  | Define and Execute AI Risk Response Actions    | ScreeningAgent           |
| COSO-CA.03         | COSO ERM  | Deploy Control Activities Over AI Processing   | ScreeningAgent           |
| COSO-INFO.04       | COSO ERM  | Use Relevant, Quality Information for AI       | DataIngestionAgent       |
| GAO-AI-ACC.01      | GAO AI    | Establish Clear Lines of Accountability        | AuditTrailAgent          |
| GAO-AI-DI.02       | GAO AI    | Verify and Maintain AI Input Data Integrity    | DataIngestionAgent       |
| GAO-AI-EX.03       | GAO AI    | Ensure AI Decisions are Explainable            | ScreeningAgent           |
| GAO-AI-TR.04       | GAO AI    | Maintain Transparency in AI Model Use          | ScreeningAgent           |
| IIA-AI-ETH.01      | IIA AI    | Embed Ethical Principles in AI Decisions       | ScreeningAgent           |
| IIA-AI-LC.02       | IIA AI    | Oversee the Full AI System Lifecycle           | AuditTrailAgent          |
| IIA-AI-IND.03      | IIA AI    | Maintain Independence of Internal Audit        | AuditTrailAgent          |
| IIA-AI-CM.04       | IIA AI    | Implement Continuous Monitoring                | ReportingAgent           |

## Implementation

- `compliance_agents/governance/frameworks.py` — Control definitions
- `compliance_agents/governance/engine.py` — Assertion engine and sweep runner

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /compliance/governance/sweep?period_hours=24` | Full cross-framework sweep |
| `GET /compliance/governance/framework/{id}` | Single framework assessment |
| `GET /compliance/governance/controls` | List all 16 controls |
| `GET /compliance/governance/controls/{control_id}` | Single control detail |
| `GET /compliance/governance/reconstruct/{screening_id}` | Full decision reconstruction (GAO-AI-TR.04) |
| `GET /compliance/governance/bias?period_hours=168` | Bias analysis (COBIT-DSS06.06) |

## How to Use This as a Rulebook

The frameworks are not separate from the agents — they ARE the agents,
expressed in governance language:

```
DataIngestionAgent   → implements COBIT-APO12.01, COSO-INFO.04, GAO-AI-DI.02
ScreeningAgent       → implements COBIT-DSS06.06, COSO-CA.03, COSO-RC.05, GAO-AI-EX.03, GAO-AI-TR.04, IIA-AI-ETH.01
AuditTrailAgent      → implements COBIT-DSS06.03, GAO-AI-ACC.01, IIA-AI-IND.03, IIA-AI-LC.02
ReportingAgent       → implements COBIT-MEA01.03, IIA-AI-CM.04
GovernanceEngine     → validates all 16 controls on demand or on schedule
```

Run `GET /compliance/governance/sweep` to get a board-ready compliance status
report across all four frameworks at any time.
