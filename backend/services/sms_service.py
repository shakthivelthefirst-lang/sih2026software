import logging
import os
import re
from typing import Any, Dict, Optional

import urllib.request
import urllib.parse
import json

logger = logging.getLogger(__name__)


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name)
    return value.strip() if value is not None else default


def normalize_mobile_number(mobile: str) -> str:
    """Normalize to 10-digit Indian mobile number."""
    value = re.sub(r"[\s().\-]", "", str(mobile or ""))
    if value.startswith("+91"):
        value = value[3:]
    elif value.startswith("91") and len(value) == 12:
        value = value[2:]
    if len(value) != 10 or value[0] not in "6789" or not value.isdigit():
        raise ValueError("Mobile number must be a valid 10-digit Indian number")
    return value


def _result(status: str, phone: str, *, message_id: Optional[str] = None,
            error_code: Optional[str] = None, error_description: Optional[str] = None,
            **extra: Any) -> Dict[str, Any]:
    return {
        "success": status in ("SUBMITTED", "SIMULATED"),
        "status": status,
        "phone": phone,
        "message_id": message_id,
        "error_code": error_code,
        "error_description": error_description,
        **extra,
    }


def send_sms(mobile: str, message: str) -> Dict[str, Any]:
    api_key = _env("FAST2SMS_API_KEY", "")
    sender_id = _env("FAST2SMS_SENDER_ID", "SURVI")
    enabled = (_env("SMS_ENABLED", "false") or "false").lower() == "true"

    # Normalize number
    try:
        number = normalize_mobile_number(mobile)
    except ValueError as e:
        return _result("INVALID_DESTINATION", mobile,
                       error_code="INVALID_DESTINATION", error_description=str(e))

    # Simulation mode when disabled or no API key
    if not enabled or not api_key:
        logger.info("[Fast2SMS] SMS simulation for number ending ...%s", number[-4:])
        return _result("SIMULATED", mobile, message_id=f"SIM-{os.urandom(4).hex()}")

    try:
        payload = {
            "route": "q",           # Quick/transactional route
            "numbers": number,
            "message": message,
            "language": "english",
            "flash": 0,
            "sender_id": sender_id,
        }
        data = urllib.parse.urlencode(payload).encode("utf-8")
        req = urllib.request.Request(
            "https://www.fast2sms.com/dev/bulkV2",
            data=data,
            headers={
                "authorization": api_key,
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode())

        logger.info("[Fast2SMS] Response: %s", body)

        if body.get("return") is True:
            request_ids = body.get("request_id") or body.get("request_ids", [])
            if isinstance(request_ids, list):
                msg_id = request_ids[0] if request_ids else "unknown"
            else:
                msg_id = str(request_ids)
            return _result("SUBMITTED", mobile, message_id=msg_id)
        else:
            err = str(body.get("message", body))
            logger.error("[Fast2SMS] Failed: %s", err)
            return _result("SUBMIT_FAILED", mobile,
                           error_code="API_ERROR", error_description=err)

    except Exception as e:
        logger.exception("[Fast2SMS] Unexpected error: %s", str(e))
        return _result("SUBMIT_FAILED", mobile,
                       error_code="EXCEPTION", error_description=str(e))


def smpp_health() -> Dict[str, Any]:
    """Health check — reports Fast2SMS configuration status."""
    api_key = _env("FAST2SMS_API_KEY", "")
    enabled = (_env("SMS_ENABLED", "false") or "false").lower() == "true"

    configured = bool(api_key) and enabled

    return {
        "provider": "Fast2SMS",
        "enabled": enabled,
        "configured": configured,
        "ready": configured,
        "api_key_set": bool(api_key),
        "mode": "LIVE" if configured else ("SIMULATION" if not enabled else "MISSING_API_KEY"),
        "connection": "LIVE" if configured else "DISABLED",
        "bind": "N/A",
        "configuration_error": None if configured else (
            "SMS_ENABLED is false or FAST2SMS_API_KEY is not set — running in simulation mode"
        ),
    }
