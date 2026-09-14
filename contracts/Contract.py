# v0.2.16
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
from genlayer import *
from dataclasses import dataclass
import json
from urllib.parse import urlparse
from datetime import datetime

UserError = gl.vm.UserError


def _addr_str(addr: Address) -> str:
    try:
        return addr.as_hex.lower()
    except Exception:
        return str(addr).lower()


def _extract_origin(url: str) -> tuple:
    u = url.strip()
    if not (u.startswith("http://") or u.startswith("https://")):
        raise UserError("URL must start with http:// or https://")
    try:
        parsed = urlparse(u)
    except Exception:
        raise UserError("Invalid URL format")

    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        raise UserError("Only http and https protocols are supported")

    if parsed.username is not None or parsed.password is not None:
        raise UserError("URL credentials are not allowed")

    hostname = parsed.hostname
    if not hostname:
        raise UserError("URL missing valid hostname")

    hostname = hostname.lower().strip()
    if not hostname or ".." in hostname or hostname.startswith(".") or hostname.endswith("."):
        raise UserError("Ambiguous or invalid hostname")

    port = parsed.port
    if port is None:
        port = 80 if scheme == "http" else 443

    return scheme, hostname, port


def _is_origin_valid(target_url: str, base_url: str) -> bool:
    t_scheme, t_host, t_port = _extract_origin(target_url)
    b_scheme, b_host, b_port = _extract_origin(base_url)

    if t_scheme != b_scheme or t_port != b_port:
        return False

    if t_host == b_host:
        return True

    if t_host.endswith("." + b_host):
        return True

    return False


def _parse_llm_json(text) -> dict:
    if isinstance(text, dict):
        return text
    if hasattr(text, "content"):
        text = text.content
    try:
        cleaned = str(text).strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        return json.loads(cleaned.strip())
    except Exception as e:
        return {"verdict": "ABORT", "confidence": 0, "reason": f"Parse error: {str(e)}"}


def _safe_parse(raw) -> dict:
    data = _parse_llm_json(raw)
    if not isinstance(data, dict):
        return None

    verdict = str(data.get("verdict", "")).strip().upper()
    if verdict not in ("SLA_COMPLIANT", "SLA_DEGRADED", "SLA_BREACHED", "ABORT"):
        return None

    conf = data.get("confidence", 0)
    if isinstance(conf, float):
        conf = int(conf)
    if not isinstance(conf, int) or not (0 <= conf <= 100):
        return None

    reason = str(data.get("reason", ""))

    # Unified 75% confidence threshold across entire pipeline
    if conf < 75 and verdict != "ABORT":
        verdict = "ABORT"
        reason = f"[low_confidence: {conf}%] " + reason

    return {
        "verdict": verdict,
        "confidence": conf,
        "reason": reason[:300],
    }


@allow_storage
@dataclass
class AgentServiceProfile:
    service_id: str
    operator: str
    service_name: str
    declared_sla_terms: str
    status_page_base: str
    total_audits: bigint


@allow_storage
@dataclass
class SLAPerformanceAudit:
    audit_id: str
    service_id: str
    telemetry_log_url: str
    status: str       # PENDING | COMPLIANT | DEGRADED | BREACHED | ESCALATED
    verdict: str      # SLA_COMPLIANT | SLA_DEGRADED | SLA_BREACHED | ABORT
    confidence: bigint
    evaluation_summary: str
    audited_epoch: bigint


class Contract(gl.Contract):
    services: TreeMap[str, AgentServiceProfile]
    audits: TreeMap[str, SLAPerformanceAudit]
    service_counter: bigint
    total_audits_logged: bigint
    sla_validity_window: bigint
    sla_registry_arbiter: str

    def __init__(self):
        self.service_counter = bigint(0)
        self.total_audits_logged = bigint(0)
        self.sla_validity_window = bigint(86400)  # 24 hours validity
        self.sla_registry_arbiter = _addr_str(gl.message.sender_address)

    def _get_current_timestamp(self) -> bigint:
        """Derive trusted timestamp from transaction execution context."""
        try:
            dt_str = str(gl.message_raw.get("datetime", ""))
            if not dt_str:
                raise UserError("Trusted timestamp unavailable: gl.message_raw missing 'datetime'")
            dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            ts = bigint(int(dt.timestamp()))
            if ts <= bigint(0):
                raise UserError("Invalid timestamp resolved")
            return ts
        except UserError:
            raise
        except Exception as e:
            raise UserError(f"Timestamp extraction failed: {str(e)}")

    @gl.public.write
    def register_service_profile(
        self,
        service_name: str,
        declared_sla_terms: str,
        status_page_base: str,
    ) -> str:
        """AI agent operator registers an endpoint or autonomous service with SLA commitments."""
        service_name = service_name.strip()
        declared_sla_terms = declared_sla_terms.strip()
        status_page_base = status_page_base.strip()

        if len(service_name) < 3:
            raise UserError("Service name too short")
        if len(declared_sla_terms) < 10:
            raise UserError("SLA commitment terms too short (min 10 chars)")

        _extract_origin(status_page_base)

        self.service_counter += bigint(1)
        sid = str(self.service_counter)

        self.services[sid] = AgentServiceProfile(
            service_id=sid,
            operator=_addr_str(gl.message.sender_address),
            service_name=service_name,
            declared_sla_terms=declared_sla_terms,
            status_page_base=status_page_base,
            total_audits=bigint(0),
        )
        return sid

    @gl.public.write
    def audit_service_sla(
        self,
        service_id: str,
        telemetry_log_url: str,
    ) -> str:
        """Trigger autonomous AI consensus to inspect public telemetry/status log against SLA terms."""
        if service_id not in self.services:
            raise UserError("Service profile not found")
        srv = self.services[service_id]

        telemetry_log_url = telemetry_log_url.strip()

        if not _is_origin_valid(telemetry_log_url, srv.status_page_base):
            raise UserError("Telemetry URL origin does not match registered service status host")

        current_ts = self._get_current_timestamp()

        srv.total_audits += bigint(1)
        self.total_audits_logged += bigint(1)
        aid = service_id + "_" + str(srv.total_audits)

        self.audits[aid] = SLAPerformanceAudit(
            audit_id=aid,
            service_id=service_id,
            telemetry_log_url=telemetry_log_url,
            status="PENDING",
            verdict="",
            confidence=bigint(0),
            evaluation_summary="",
            audited_epoch=current_ts,
        )
        self.services[service_id] = srv

        s_name = str(srv.service_name)
        s_terms = str(srv.declared_sla_terms)
        u_log = str(telemetry_log_url)

        def leader_fn():
            try:
                res = gl.nondet.web.render(u_log, mode="text")
                log_text = res.content if hasattr(res, "content") else str(res)
                if not log_text or len(log_text.strip()) < 30:
                    return {"verdict": "ABORT", "confidence": 0, "reason": "Telemetry page returned empty text"}
                if any(err in log_text[:400].lower() for err in ["404 not found", "error 404", "server offline"]):
                    return {"verdict": "ABORT", "confidence": 0, "reason": "Telemetry page unreachable/404"}
            except Exception as e:
                return {"verdict": "ABORT", "confidence": 0, "reason": f"Web fetch error: {str(e)}"}

            prompt = f"""
SYSTEM: You are the Autonomous Decentralized SLA Performance & Uptime Verifier.
Audit the target AI Agent/RPC endpoint performance log against its declared SLA commitments.

SERVICE NAME: {s_name}
DECLARED SLA TERMS:
{s_terms}

FETCHED TELEMETRY & HEALTH REPORT:
{log_text[:4000]}

EVIDENCE BINDING MANDATE:
1. Verify that the telemetry evidence above explicitly and unambiguously corresponds to SERVICE NAME '{s_name}'.
2. If the telemetry report is for an unrelated endpoint or does not mention/validate metrics for '{s_name}', you MUST output verdict 'ABORT' with reason 'telemetry_target_mismatch'.

Classification Rules:
- SLA_COMPLIANT (conf >= 75): Service meets uptime requirements, healthy response times, zero major error rates, and adheres to declared terms.
- SLA_DEGRADED (conf >= 75): Partial service degradation, transient 429 rate limits, elevated latency, but still functional.
- SLA_BREACHED (conf >= 75): Severe outages, sustained 5xx server errors, unhandled exceptions, or direct violation of uptime guarantees.
- ABORT: Telemetry target mismatch, status log requires login, captcha-blocked, rate-limited, or unreadable.

OUTPUT ONLY STRICT JSON:
{{
  "verdict": "SLA_COMPLIANT" | "SLA_DEGRADED" | "SLA_BREACHED" | "ABORT",
  "confidence": 0-100,
  "reason": "max 300 chars technical performance justification"
}}
"""
            try:
                raw1 = gl.nondet.exec_prompt(prompt, response_format="json")
                raw2 = gl.nondet.exec_prompt(prompt, response_format="json")

                p1 = _safe_parse(raw1)
                p2 = _safe_parse(raw2)

                if p1 is None or p2 is None:
                    return {"verdict": "ABORT", "confidence": 0, "reason": "parse_failed"}

                if p1["verdict"] != p2["verdict"]:
                    return {"verdict": "ABORT", "confidence": 0, "reason": "multi_sample_divergence"}

                p1["confidence"] = (p1["confidence"] + p2["confidence"]) // 2
                return p1
            except Exception as e:
                return {"verdict": "ABORT", "confidence": 0, "reason": f"LLM error: {str(e)}"}

        def validator_fn(leader_res) -> bool:
            if not isinstance(leader_res, gl.vm.Return):
                return False

            leader_data = leader_res.calldata if hasattr(leader_res, "calldata") else leader_res
            leader = _safe_parse(leader_data)
            if leader is None:
                return False

            mine = _safe_parse(leader_fn())
            if mine is None:
                return False

            return (
                mine["verdict"] == leader["verdict"]
                and (mine["confidence"] >= 75) == (leader["confidence"] >= 75)
            )

        result_raw = gl.vm.run_nondet(leader_fn, validator_fn)
        result = _safe_parse(result_raw)

        if result is None:
            result = {"verdict": "ABORT", "confidence": 0, "reason": "adjudication_failed"}

        verdict = result["verdict"]
        confidence = result["confidence"]
        reason = result["reason"]

        # Deterministic post-consensus normalization
        if confidence < 75 and verdict != "ABORT":
            verdict = "ABORT"

        audit = self.audits[aid]
        audit.verdict = verdict
        audit.confidence = bigint(confidence)
        audit.evaluation_summary = reason

        if verdict == "SLA_COMPLIANT":
            audit.status = "COMPLIANT"
        elif verdict == "SLA_DEGRADED":
            audit.status = "DEGRADED"
        elif verdict == "SLA_BREACHED":
            audit.status = "BREACHED"
        else:
            audit.status = "ESCALATED"

        self.audits[aid] = audit
        return aid

    @gl.public.write
    def resolve_escalated_audit(
        self,
        audit_id: str,
        manual_status: str,
        override_reason: str,
    ) -> None:
        """Authorized SLA arbiter resolves an ESCALATED audit due to temporary connection drops."""
        if audit_id not in self.audits:
            raise UserError("Audit record not found")
        audit = self.audits[audit_id]

        if audit.status != "ESCALATED":
            raise UserError("Audit is not in ESCALATED state")

        sender = _addr_str(gl.message.sender_address)
        if sender != self.sla_registry_arbiter:
            raise UserError("Only authorized arbiter can resolve escalated audits")

        s_upper = manual_status.strip().upper()
        if s_upper not in ("COMPLIANT", "DEGRADED", "BREACHED"):
            raise UserError("Invalid manual SLA status")

        audit.status = s_upper
        audit.verdict = f"RESOLVED_MANUALLY_{s_upper}"
        audit.evaluation_summary = f"Arbiter override ({sender}): {override_reason[:200]}"
        self.audits[audit_id] = audit

    @gl.public.view
    def is_service_healthy(self, audit_id: str) -> bool:
        """Lightweight status query enforcing report freshness."""
        if audit_id not in self.audits:
            return False
        a = self.audits[audit_id]
        if a.status != "COMPLIANT":
            return False
        current_ts = self._get_current_timestamp()
        if (current_ts - a.audited_epoch) > self.sla_validity_window:
            return False
        return True

    @gl.public.view
    def get_service(self, service_id: str) -> str:
        if service_id not in self.services:
            raise UserError("Service profile not found")
        s = self.services[service_id]
        return json.dumps({
            "service_id": s.service_id,
            "operator": s.operator,
            "service_name": s.service_name,
            "declared_sla_terms": s.declared_sla_terms,
            "status_page_base": s.status_page_base,
            "total_audits": str(s.total_audits),
        })

    @gl.public.view
    def get_audit(self, audit_id: str) -> str:
        if audit_id not in self.audits:
            raise UserError("Audit record not found")
        a = self.audits[audit_id]
        return json.dumps({
            "audit_id": a.audit_id,
            "service_id": a.service_id,
            "telemetry_log_url": a.telemetry_log_url,
            "status": a.status,
            "verdict": a.verdict,
            "confidence": str(a.confidence),
            "evaluation_summary": a.evaluation_summary,
            "audited_epoch": str(a.audited_epoch),
        })

    @gl.public.view
    def get_stats(self) -> str:
        return json.dumps({
            "total_registered_services": str(self.service_counter),
            "total_audits_logged": str(self.total_audits_logged),
            "sla_validity_window_seconds": str(self.sla_validity_window),
            "sla_registry_arbiter": self.sla_registry_arbiter,
        })
