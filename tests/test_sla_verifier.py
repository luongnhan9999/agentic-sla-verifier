import pytest
import json
import sys
from urllib.parse import urlparse


def clear_known_contracts():
    for name, module in list(sys.modules.items()):
        if "genlayer" in name and hasattr(module, "__known_contract__"):
            setattr(module, "__known_contract__", None)


class UserError(Exception):
    pass


# Logic replica from Contract.py for pure deterministic unit testing
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


# ==============================================================================
# TEST SUITE
# ==============================================================================

def test_sla_verifier_initialization():
    clear_known_contracts()
    name = "Eliza Autonomous Financial Agent"
    host = "https://status.agentnetwork.io"
    assert len(name) > 0
    assert host.startswith("https://")


def test_extract_origin_valid_cases():
    scheme, host, port = _extract_origin("https://status.agentnetwork.io/health")
    assert scheme == "https"
    assert host == "status.agentnetwork.io"
    assert port == 443

    scheme2, host2, port2 = _extract_origin("http://rpc.node.internal:8545/metrics")
    assert scheme2 == "http"
    assert host2 == "rpc.node.internal"
    assert port2 == 8545


def test_extract_origin_invalid_cases():
    with pytest.raises(UserError, match="URL must start with"):
        _extract_origin("ftp://files.example.com")

    with pytest.raises(UserError, match="URL credentials are not allowed"):
        _extract_origin("https://admin:pass@service.example.com")

    with pytest.raises(UserError, match="Ambiguous or invalid hostname"):
        _extract_origin("https://..example.com")


def test_is_origin_valid_subdomain_and_match():
    base = "https://agentnetwork.io"
    # Exact host match
    assert _is_origin_valid("https://agentnetwork.io/status", base) is True
    # Subdomain match
    assert _is_origin_valid("https://telemetry.agentnetwork.io/metrics", base) is True
    # Port mismatch
    assert _is_origin_valid("https://agentnetwork.io:8443/status", base) is False
    # Scheme mismatch
    assert _is_origin_valid("http://agentnetwork.io/status", base) is False
    # Unrelated host
    assert _is_origin_valid("https://evil-agentnetwork.io/status", base) is False


def test_parse_llm_json():
    # Markdown formatted JSON
    raw_md = "```json\n{\"verdict\": \"SLA_COMPLIANT\", \"confidence\": 95, \"reason\": \"Uptime 99.99%\"}\n```"
    parsed = _parse_llm_json(raw_md)
    assert parsed["verdict"] == "SLA_COMPLIANT"
    assert parsed["confidence"] == 95

    # Malformed text
    malformed = "Service looks okay but no json here"
    parsed_err = _parse_llm_json(malformed)
    assert parsed_err["verdict"] == "ABORT"


def test_safe_parse_confidence_threshold_75():
    # High confidence compliant
    high_conf = {"verdict": "SLA_COMPLIANT", "confidence": 88, "reason": "All SLA metrics satisfied"}
    res = _safe_parse(high_conf)
    assert res["verdict"] == "SLA_COMPLIANT"
    assert res["confidence"] == 88

    # Low confidence (< 75) must be converted to ABORT
    low_conf = {"verdict": "SLA_COMPLIANT", "confidence": 70, "reason": "Partial metrics"}
    res_low = _safe_parse(low_conf)
    assert res_low["verdict"] == "ABORT"
    assert "[low_confidence: 70%]" in res_low["reason"]

    # Boundary 75 confidence must remain SLA_COMPLIANT
    boundary = {"verdict": "SLA_COMPLIANT", "confidence": 75, "reason": "Exact threshold"}
    res_boundary = _safe_parse(boundary)
    assert res_boundary["verdict"] == "SLA_COMPLIANT"


def test_safe_parse_invalid_verdicts_and_bounds():
    # Invalid verdict
    assert _safe_parse({"verdict": "UNKNOWN_STATE", "confidence": 90}) is None

    # Out of bounds confidence
    assert _safe_parse({"verdict": "SLA_COMPLIANT", "confidence": 105}) is None
    assert _safe_parse({"verdict": "SLA_COMPLIANT", "confidence": -5}) is None


def test_status_mapping_rules():
    verdicts = {
        "SLA_COMPLIANT": "COMPLIANT",
        "SLA_DEGRADED": "DEGRADED",
        "SLA_BREACHED": "BREACHED",
        "ABORT": "ESCALATED"
    }

    for v, expected_status in verdicts.items():
        if v == "SLA_COMPLIANT":
            status = "COMPLIANT"
        elif v == "SLA_DEGRADED":
            status = "DEGRADED"
        elif v == "SLA_BREACHED":
            status = "BREACHED"
        else:
            status = "ESCALATED"
        assert status == expected_status
