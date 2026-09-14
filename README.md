# AgenticSLAVerifier (Autonomous AI Agent SLA & Reliability Registry)

[![GenLayer Intelligent Contract](https://img.shields.io/badge/GenLayer-Intelligent%20Contract-8A2BE2.svg)](https://genlayer.com)
[![Network](https://img.shields.io/badge/Network-GenLayer%20Studionet-blue.svg)](https://studio.genlayer.com)
[![Chain ID](https://img.shields.io/badge/Chain%20ID-61999-brightgreen.svg)](https://studio.genlayer.com)
[![Status](https://img.shields.io/badge/Deployment-SUCCESS%20(Status%205)-success.svg)](https://studio.genlayer.com)
[![Architecture](https://img.shields.io/badge/Architecture-Zero--Custody%20Performance%20Oracle-orange.svg)](#architecture)

> **AgenticSLAVerifier** is an autonomous on-chain Service-Level Agreement (SLA) & Reliability Verification Oracle built on **GenLayer**. It serves the emerging autonomous agent economy (AI Agents, Decentralized RPC nodes, and DePIN compute providers) by autonomously auditing endpoint health and telemetry logs directly against registered SLA commitments using multi-sample LLM consensus.

---

## 🚀 Live Studionet Deployment

- **CONTRACT_ADDRESS**: `0xfe4AABA6a786E33fb44fa53C2c8985A8133D3825`
- **NETWORK**: `studionet`
- **Chain ID**: `61999`
- **RPC Endpoint**: `https://studio.genlayer.com/api`
- **Consensus Receipt Status**: `5` (ACCEPTED / FINALIZED)
- **Execution Result**: `SUCCESS`

### Real On-Chain Query Result
Querying view function `get_stats()` on Studionet:
```python
from genlayer_py import create_client, create_account, generate_private_key, studionet
account = create_account(generate_private_key())
client = create_client(studionet, account=account)
stats = client.read_contract(
    address="0xfe4AABA6a786E33fb44fa53C2c8985A8133D3825",
    function_name="get_stats",
    args=[]
)
print("Stats:", stats)
```
**Real On-Chain Output:**
```json
{"total_registered_services": "0", "total_audits_logged": "0", "sla_validity_window_seconds": "86400", "sla_registry_arbiter": "0x52c5e913fc54d00cba5df3312268bf66035661f8"}
```

---

### 💡 Illustrative End-to-End Workflow Example (Worked Example)

Below is an illustrative execution trace demonstrating the lifecycle of an AI agent SLA audit:

#### 1. Register AI Agent Service Profile
```python
# Operator registers their autonomous agent endpoint and SLA requirements
tx = client.write_contract(
    address="0xfe4AABA6a786E33fb44fa53C2c8985A8133D3825",
    function_name="register_service_profile",
    args=[
        "Eliza Autonomous Financial Agent",
        "Uptime >= 99.9%, p99 response time < 500ms, zero persistent 5xx errors",
        "https://status.agentnetwork.io"
    ]
)
```
*(Illustrative Expected Return)*: `"1"` (allocated unique service ID)

#### 2. Trigger Autonomous SLA Audit via AI Consensus
```python
# Downstream protocol or automated keeper triggers an SLA performance verification
tx = client.write_contract(
    address="0xfe4AABA6a786E33fb44fa53C2c8985A8133D3825",
    function_name="audit_service_sla",
    args=["1", "https://status.agentnetwork.io/health/v1"]
)
```
*(Illustrative Expected Return)*: `"1_1"` (allocated audit ID `service_id + "_" + audit_counter`)

#### 3. Inspect Audit Attestation
```python
audit_json = client.read_contract(
    address="0xfe4AABA6a786E33fb44fa53C2c8985A8133D3825",
    function_name="get_audit",
    args=["1_1"]
)
```
*(Illustrative Expected Output)*:
```json
{
  "audit_id": "1_1",
  "service_id": "1",
  "telemetry_log_url": "https://status.agentnetwork.io/health/v1",
  "status": "COMPLIANT",
  "verdict": "SLA_COMPLIANT",
  "confidence": "92",
  "evaluation_summary": "Telemetry shows 99.98% uptime over rolling 24h, avg response latency 180ms, 0 server errors detected.",
  "audited_epoch": "1726300000"
}
```

#### 4. Automated Smart Contract Routing Check
```python
# Payment streaming or routing contract verifies service health (checks COMPLIANT status and freshness window):
is_healthy = client.read_contract(
    address="0xfe4AABA6a786E33fb44fa53C2c8985A8133D3825",
    function_name="is_service_healthy",
    args=["1_1"]
)
```
*(Illustrative Expected Output)*: `True`

---

## 🧠 How Consensus Works: Agreement on MEANING, Not Format

A critical pitfall in decentralized AI oracles is "format-only" validation (merely checking that an LLM response is valid JSON or contains expected keys). **AgenticSLAVerifier strictly validates semantic MEANING**:

1. **Independent Evaluation in `validator_fn()`**:
   The validator node does not blindly trust the leader's data. It re-runs `leader_fn()` locally, fetching live web telemetry and executing multi-sample LLM reasoning independently.
2. **Semantic Verdict Equivalence**:
   Validators verify that both nodes arrived at the exact same qualitative verdict:
   ```python
   mine["verdict"] == leader["verdict"]
   ```
   If the leader claims `SLA_COMPLIANT` but the validator observes latency spikes classifying the state as `SLA_DEGRADED`, consensus fails (`return False`).
3. **High-Confidence Equivalence**:
   Validators enforce that both nodes independently met the strict 75% confidence threshold:
   ```python
   (mine["confidence"] >= 75) == (leader["confidence"] >= 75)
   ```
4. **Leader Multi-Sample Self-Consistency**:
   Before proposing a transaction, the leader executes two independent non-deterministic prompts (`raw1`, `raw2`). If the verdicts diverge between the two samples, the leader immediately collapses the verdict to `ABORT`, preventing hallucinated submissions.
5. **Deterministic Post-Consensus Normalization**:
   Even after consensus, a deterministic check clamps confidence < 75 to `ABORT`, ensuring safety under all edge conditions.

---

## 💡 Core Architecture & Business Logic

### 1. Zero-Custody / No Escrow Payouts
Traditional SLA models frequently rely on deposit custody, staking penalties, or escrow funds that are susceptible to drainage or flash-loan exploits. **AgenticSLAVerifier eliminates financial custody**:
- Holds **zero user deposits** or escrow pools.
- Acts as a **Pure Performance Attestation Registry & Uptime Oracle**.
- Downstream DeFi protocols, AI agent marketplaces, or payment streaming channels (e.g., Superfluid / Sablier) read `is_service_healthy()` to programmatically gate payments, route queries, or throttle traffic.

### 2. Deep Telemetry & Unstructured Log Auditing
Rather than checking binary ping signals, the contract validators crawl actual telemetry feeds, health check endpoints, and status reports:
- Parses unstructured HTTP metrics, error logs, and JSON-RPC messages.
- Evaluates latency, rate-limiting (HTTP 429), server exceptions (HTTP 5xx), and sustained degradation.
- Compares findings against natural-language declared SLA terms (e.g. *“99.9% uptime, <250ms p99 latency, maximum 5 errors per 10k requests”*).

### 3. Strict 75% Confidence Single-Threshold Consensus
To eliminate validator ambiguity and avoid consensus divergence, the contract enforces a single **75% confidence threshold** across the entire pipeline:
1. **Prompt Rules**: Explicit instructions mandate `conf >= 75` for `SLA_COMPLIANT`, `SLA_DEGRADED`, and `SLA_BREACHED`.
2. **Deterministic Parser**: Any output below 75% is automatically downgraded to `ABORT` with reason `[low_confidence: X%]`.
3. **Multi-Sample Divergence Check**: In `leader_fn()`, the leader executes two LLM evaluations. If verdicts disagree or average confidence falls below 75%, it immediately yields `ABORT`.
4. **Validator Equivalence**: Validators verify that the verdict matches and both nodes agreed on the `confidence >= 75` bucket.
5. **Post-Consensus Normalization**: Deterministic safety clamp forces `ABORT` if final confidence is below 75%.

### 4. Robust Origin & Hostname Validation
To defend against malicious redirects, SSRF, and domain spoofing:
- Enforces HTTP/HTTPS protocol checks via `urllib.parse.urlparse`.
- Explicitly rejects embedded credentials (`username:password@`).
- Validates that telemetry URLs match or are exact subdomains of the registered base origin (`_is_origin_valid`).

---

## ⚖️ Architectural Differentiation & Novelty Matrix

To guarantee genuine innovation and avoid redundancy with traditional contract designs (e.g. escrow vaults, bounty platforms, or refund pools):

| Dimension | Traditional SLA Smart Contracts (e.g. Escrow / Insurance) | AgenticSLAVerifier (This Project) |
| :--- | :--- | :--- |
| **Custody Model** | Custodial: Locks funds, collateral, and handles payouts. | **Zero-Custody**: Zero funds locked, zero escrow fees. Pure performance attestation oracle. |
| **Target Entities** | Web2 SaaS clients vs Cloud providers (Human parties). | **Autonomous AI Agents**, Decentralized RPC nodes, and DePIN compute networks. |
| **Storage Structure** | Escrow accounts, locked balances, payout ratios (`payout_pct`). | **Endpoint Registry (`AgentServiceProfile`) & Session Audit Logs (`SLAPerformanceAudit`)**. |
| **Input Data** | Binary pings or manual claim tickets. | **Live telemetry feeds, raw JSON-RPC logs, and unstructured health check status pages**. |
| **Output / Verdicts** | Financial redistribution: `FULL_PAYOUT`, `PENALIZED_PARTIAL`, `ZERO_PAYOUT`. | Multi-tier SLA status classification: **`SLA_COMPLIANT`**, **`SLA_DEGRADED`**, **`SLA_BREACHED`**. |
| **Composability** | Terminal escrow settlement. | **High-frequency on-chain Oracle**: External contracts call `is_service_healthy(audit_id)` for dynamic agent routing. |

---

## 📊 State Machine & Classification

```
   [ Register Service Profile ]
                │
                ▼
      [ Trigger SLA Audit ]
                │
         [ leader_fn() ]
   ├── Fetch Web Telemetry (`gl.nondet.web.render`)
   ├── Multi-sample LLM consensus (`gl.nondet.exec_prompt`)
   └── Validation: confidence >= 75%
                │
       [ validator_fn() ]
                │
        Consensus Result
        ├── SLA_COMPLIANT ──> Status: COMPLIANT
        ├── SLA_DEGRADED  ──> Status: DEGRADED
        ├── SLA_BREACHED  ──> Status: BREACHED
        └── ABORT         ──> Status: ESCALATED
                                    │
                       (Authorized Arbiter Override)
                                    ▼
                          RESOLVED_MANUALLY_*
```

---

## 📁 Repository Structure

```
.
├── contracts/
│   └── Contract.py               # Main GenLayer Intelligent Contract
├── scripts/
│   └── deploy_studionet.py       # Automated deployment & verification script
├── tests/
│   └── test_sla_verifier.py      # Full unit test suite
├── deployment.json               # On-chain deployment receipt & consensus proof
├── gltest.config.yaml            # GenLayer test network configuration
├── requirements-dev.txt          # Python dependencies
├── .gitignore                    # Git ignore file
└── README.md                     # Project documentation
```

---

## 🛠️ Public Contract Interface

### Write Methods
- `register_service_profile(service_name: str, declared_sla_terms: str, status_page_base: str) -> str`:
  Registers a new AI agent or RPC service endpoint with its SLA requirements. Returns unique `service_id`.
- `audit_service_sla(service_id: str, telemetry_log_url: str) -> str`:
  Triggers non-deterministic validator consensus to fetch the telemetry log, run AI evaluation, and attest compliance on-chain. Returns `audit_id`.
- `resolve_escalated_audit(audit_id: str, manual_status: str, override_reason: str) -> None`:
  Emergency fallback: allows the authorized registry arbiter to resolve `ESCALATED` audits caused by transient network outages or anti-bot captchas.

### View Methods
- `is_service_healthy(audit_id: str) -> bool`:
  Returns `True` if audit status is `COMPLIANT`. Suitable for automated payment gateways or agent routing routers.
- `get_service(service_id: str) -> str`:
  Returns JSON metadata for a registered service profile.
- `get_audit(audit_id: str) -> str`:
  Returns full JSON audit record, including verdict, confidence, status, and LLM evaluation summary.
- `get_stats() -> str`:
  Returns total registered services and total completed audits.

---

## 🧪 Testing

The unit test suite verifies origin validation, security boundaries, JSON parsing, prompt sanitization, confidence thresholding, and state transitions.

```bash
# Run tests
pytest tests/test_sla_verifier.py -v
```

### Test Results
```
tests/test_sla_verifier.py::test_sla_verifier_initialization PASSED      [ 12%]
tests/test_sla_verifier.py::test_extract_origin_valid_cases PASSED       [ 25%]
tests/test_sla_verifier.py::test_extract_origin_invalid_cases PASSED     [ 37%]
tests/test_sla_verifier.py::test_is_origin_valid_subdomain_and_match PASSED [ 50%]
tests/test_sla_verifier.py::test_parse_llm_json PASSED                   [ 62%]
tests/test_sla_verifier.py::test_safe_parse_confidence_threshold_75 PASSED [ 75%]
tests/test_sla_verifier.py::test_safe_parse_invalid_verdicts_and_bounds PASSED [ 87%]
tests/test_sla_verifier.py::test_status_mapping_rules PASSED             [100%]

============================== 8 passed in 0.15s ==============================
```

---

## 🚢 Deploying to GenLayer Studionet

```bash
# Install dependencies
pip install -r requirements-dev.txt

# Run deployment script
python scripts/deploy_studionet.py
```

---

## 📜 Submission Details

- **Project**: `AgenticSLAVerifier`
- **Category**: Intelligent Contracts
- **Framework**: GenLayer GenVM (Python 3.13 / py-genlayer 0.16.x)
- **Deployment Status**: Finalized on Studionet
