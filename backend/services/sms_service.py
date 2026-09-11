import logging
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

import smpplib
import smpplib.client
import smpplib.consts
import smpplib.gsm

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SMPPConfig:
    enabled: bool
    host: str
    port: int
    system_id: str
    password: str
    source_addr: str
    source_addr_ton: int
    source_addr_npi: int
    dest_addr_ton: int
    dest_addr_npi: int
    destination_prefix: str
    timeout: int
    system_type: Optional[str]
    interface_version: Optional[int]
    service_type: str
    protocol_id: int
    priority_flag: int
    registered_delivery: int
    data_coding: Optional[int]
    esm_class: Optional[int]
    replace_if_present: int


def _env(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name)
    return value.strip() if value is not None else default


def _int_env(name: str, default: Optional[int]) -> Optional[int]:
    value = _env(name)
    if value in (None, ""):
        return default
    try:
        return int(value, 0)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def load_config() -> SMPPConfig:
    return SMPPConfig(
        enabled=(_env("SMPP_ENABLED", "false") or "false").lower() == "true",
        host=_env("SMPP_HOST", "") or "",
        port=_int_env("SMPP_PORT", 2775) or 2775,
        system_id=_env("SMPP_SYSTEM_ID", "") or "",
        password=_env("SMPP_PASSWORD", "") or "",
        source_addr=_env("SMPP_SOURCE_ADDR", "") or "",
        source_addr_ton=_int_env("SMPP_SOURCE_ADDR_TON", smpplib.consts.SMPP_TON_ALNUM) or 0,
        source_addr_npi=_int_env("SMPP_SOURCE_ADDR_NPI", smpplib.consts.SMPP_NPI_UNK) or 0,
        dest_addr_ton=_int_env("SMPP_DEST_ADDR_TON", smpplib.consts.SMPP_TON_INTL) or 0,
        dest_addr_npi=_int_env("SMPP_DEST_ADDR_NPI", smpplib.consts.SMPP_NPI_ISDN) or 0,
        destination_prefix=_env("SMPP_DESTINATION_PREFIX", "91") or "",
        timeout=_int_env("SMPP_TIMEOUT", 5) or 5,
        system_type=_env("SMPP_SYSTEM_TYPE"),
        interface_version=_int_env("SMPP_INTERFACE_VERSION", None),
        service_type=_env("SMPP_SERVICE_TYPE", "") or "",
        protocol_id=_int_env("SMPP_PROTOCOL_ID", 0) or 0,
        priority_flag=_int_env("SMPP_PRIORITY_FLAG", 0) or 0,
        registered_delivery=_int_env("SMPP_REGISTERED_DELIVERY", 1) or 0,
        data_coding=_int_env("SMPP_DATA_CODING", None),
        esm_class=_int_env("SMPP_ESM_CLASS", None),
        replace_if_present=_int_env("SMPP_REPLACE_IF_PRESENT", 0) or 0,
    )


def _status_name(status: Optional[int]) -> Optional[str]:
    if status is None:
        return None
    for name, value in vars(smpplib.consts).items():
        if name.startswith("SMPP_ESME_") and value == status:
            return name
    return f"0x{status:08X}"


def _status_description(status: Optional[int]) -> Optional[str]:
    if status is None:
        return None
    return smpplib.consts.DESCRIPTIONS.get(status, "Unknown SMPP status")


def _exception_status(error: Exception) -> Optional[int]:
    for value in reversed(getattr(error, "args", ())):
        if isinstance(value, int):
            return value
    return None


def normalize_mobile_number(mobile: str, destination_prefix: str = "91") -> str:
    value = re.sub(r"[\s().-]", "", str(mobile or ""))
    if value.startswith("+"):
        if not value.startswith("+91"):
            raise ValueError("Only Indian mobile numbers are supported")
        value = value[3:]
    elif value.startswith("91") and len(value) == 12:
        value = value[2:]
    if len(value) != 10 or value[0] not in "6789" or not value.isdigit():
        raise ValueError("Mobile number must be a valid 10-digit Indian number")
    return f"{destination_prefix}{value}" if destination_prefix else value


def _configuration_error(config: SMPPConfig) -> Optional[str]:
    if not config.enabled:
        return None
    missing = [name for name, value in (
        ("SMPP_HOST", config.host),
        ("SMPP_SYSTEM_ID", config.system_id),
        ("SMPP_PASSWORD", config.password),
        ("SMPP_SOURCE_ADDR", config.source_addr),
    ) if not value]
    return "Missing SMPP configuration: " + ", ".join(missing) if missing else None


def _result(status: str, phone: str, *, message_id: Optional[str] = None,
            command_status: Optional[str] = None, error_code: Optional[str] = None,
            error_description: Optional[str] = None, exception_type: Optional[str] = None,
            exception_message: Optional[str] = None, retryable: bool = False,
            **extra: Any) -> Dict[str, Any]:
    return {
        "success": status in ("SUBMITTED", "SIMULATED"),
        "status": status,
        "phone": phone,
        "message_id": message_id,
        "smpp_command_status": command_status,
        "error_code": error_code,
        "error_description": error_description,
        "exception_type": exception_type,
        "exception_message": exception_message,
        "retryable": retryable,
        **extra,
    }


def send_sms(mobile: str, message: str) -> Dict[str, Any]:
    config = load_config()
    if not config.enabled:
        logger.info("[SMPP] Disabled; SMS simulation requested for phone_suffix=%s", str(mobile)[-4:])
        return _result("SIMULATED", mobile, message_id=f"SIM-{os.urandom(4).hex()}")

    try:
        destination = normalize_mobile_number(mobile, config.destination_prefix)
    except ValueError as error:
        return _result("INVALID_DESTINATION", mobile, error_code="INVALID_DESTINATION",
                       error_description=str(error), exception_type=type(error).__name__,
                       exception_message=str(error))

    configuration_error = _configuration_error(config)
    if configuration_error:
        logger.error("[SMPP] SMPP_CONFIGURATION_ERROR: %s", configuration_error)
        return _result("SMPP_CONFIGURATION_ERROR", mobile, error_code="SMPP_CONFIGURATION_ERROR",
                       error_description=configuration_error)

    client = None
    phase = "connect"
    try:
        logger.info("[SMPP] Connecting host=%s port=%s", config.host, config.port)
        client = smpplib.client.Client(config.host, config.port, timeout=config.timeout)
        client.connect()
        logger.info("[SMPP] Connected")

        bind_kwargs = {"system_id": config.system_id, "password": config.password}
        if config.system_type is not None:
            bind_kwargs["system_type"] = config.system_type
        if config.interface_version is not None:
            bind_kwargs["interface_version"] = config.interface_version
        logger.info("[SMPP] Binding")
        phase = "bind"
        bind_response = client.bind_transceiver(**bind_kwargs)
        bind_status = getattr(bind_response, "status", None)
        if bind_status != smpplib.consts.SMPP_ESME_ROK:
            code = _status_name(bind_status)
            logger.error("[SMPP] SMPP_BIND_FAILED command_status=%s", code)
            return _result("SMPP_BIND_FAILED", mobile, command_status=code,
                           error_code=code, error_description=_status_description(bind_status))
        logger.info("[SMPP] Bind successful")

        parts, encoding_flag, msg_type_flag = smpplib.gsm.make_parts(message)
        submit_ids = []
        for part in parts:
            phase = "submit"
            submit_kwargs = {
                "service_type": config.service_type,
                "source_addr_ton": config.source_addr_ton,
                "source_addr_npi": config.source_addr_npi,
                "source_addr": config.source_addr,
                "dest_addr_ton": config.dest_addr_ton,
                "dest_addr_npi": config.dest_addr_npi,
                "destination_addr": destination,
                "short_message": part,
                "data_coding": config.data_coding if config.data_coding is not None else encoding_flag,
                "esm_class": config.esm_class if config.esm_class is not None else msg_type_flag,
                "protocol_id": config.protocol_id,
                "priority_flag": config.priority_flag,
                "registered_delivery": config.registered_delivery,
                "replace_if_present_flag": config.replace_if_present,
            }
            logger.info("[SMPP] Submitting message destination_suffix=%s", destination[-4:])
            client.send_message(**submit_kwargs)
            response_pdu = client.read_pdu()
            response_status = getattr(response_pdu, "status", None)
            response_code = _status_name(response_status)
            message_id = getattr(response_pdu, "message_id", None)
            logger.info("[SMPP] submit_sm_resp command_status=%s message_id=%s", response_code, message_id)
            response_is_submit = getattr(response_pdu, "command", None) == "submit_sm_resp"
            if not response_is_submit or response_status != smpplib.consts.SMPP_ESME_ROK:
                return _result("SMPP_SUBMIT_FAILED", mobile, command_status=response_code,
                               error_code=response_code if response_is_submit else "MALFORMED_RESPONSE",
                               error_description=_status_description(response_status) or "Malformed submit_sm_resp",
                               retryable=response_status == smpplib.consts.SMPP_ESME_RTHROTTLED)
            if not message_id:
                return _result("SMPP_SUBMIT_FAILED", mobile, command_status=response_code,
                               error_code="MALFORMED_RESPONSE", error_description="submit_sm_resp did not include message_id")
            submit_ids.append(str(message_id))

        return _result("SUBMITTED", mobile, message_id=submit_ids[-1],
                       command_status="SMPP_ESME_ROK", message_ids=submit_ids)
    except smpplib.exceptions.PDUError as error:
        status = _exception_status(error)
        code = _status_name(status) or "SMPP_PDU_ERROR"
        failure_status = "SMPP_BIND_FAILED" if phase == "bind" else "SMPP_SUBMIT_FAILED"
        logger.error("[SMPP] %s error_code=%s description=%s", failure_status, code, str(error))
        return _result(failure_status, mobile, command_status=code, error_code=code,
                       error_description=_status_description(status) or str(error),
                       exception_type=type(error).__name__, exception_message=str(error))
    except (smpplib.exceptions.ConnectionError, TimeoutError, OSError) as error:
        logger.error("[SMPP] Connection failed exception=%s message=%s", type(error).__name__, str(error))
        return _result("SMPP_CONNECTION_FAILED", mobile, error_code="SMPP_CONNECTION_FAILED",
                       error_description=str(error) or "Unable to connect to SMPP server",
                       exception_type=type(error).__name__, exception_message=str(error), retryable=True)
    except Exception as error:
        logger.exception("[SMPP] Unexpected failure exception=%s", type(error).__name__)
        return _result("SMPP_SUBMIT_FAILED", mobile, error_code="SMPP_UNEXPECTED_ERROR",
                       error_description=str(error), exception_type=type(error).__name__,
                       exception_message=str(error))
    finally:
        if client is not None:
            try:
                client.unbind()
            except Exception:
                pass
            try:
                client.disconnect()
            except Exception:
                pass


def smpp_health() -> Dict[str, Any]:
    config = load_config()
    configuration_error = _configuration_error(config)
    result = {
        "configured": config.enabled and configuration_error is None,
        "enabled": config.enabled,
        "host_configured": bool(config.host),
        "port_configured": bool(config.port),
        "credentials_configured": bool(config.system_id and config.password),
        "source_configured": bool(config.source_addr),
        "connection": "DISABLED" if not config.enabled else "NOT_CHECKED",
        "bind": "DISABLED" if not config.enabled else "NOT_CHECKED",
        "ready": False,
        "configuration_error": configuration_error,
    }
    if configuration_error or not config.enabled:
        return result

    client = None
    try:
        client = smpplib.client.Client(config.host, config.port, timeout=config.timeout)
        client.connect()
        result["connection"] = "CONNECTED"
        bind_kwargs = {"system_id": config.system_id, "password": config.password}
        if config.system_type is not None:
            bind_kwargs["system_type"] = config.system_type
        if config.interface_version is not None:
            bind_kwargs["interface_version"] = config.interface_version
        response = client.bind_transceiver(**bind_kwargs)
        status = getattr(response, "status", None)
        result["bind"] = "BIND_SUCCESS" if status == smpplib.consts.SMPP_ESME_ROK else "BIND_FAILED"
        result["bind_command_status"] = _status_name(status)
        result["bind_error_description"] = _status_description(status)
        result["ready"] = result["bind"] == "BIND_SUCCESS"
    except smpplib.exceptions.PDUError as error:
        status = _exception_status(error)
        result["bind"] = "BIND_FAILED" if result["connection"] == "CONNECTED" else "NOT_CHECKED"
        result["bind_command_status"] = _status_name(status) or "SMPP_PDU_ERROR"
        result["bind_error_description"] = _status_description(status) or str(error)
    except (smpplib.exceptions.ConnectionError, TimeoutError, OSError) as error:
        result["connection"] = "CONNECTION_FAILED"
        result["connection_error"] = str(error) or "Unable to connect to SMPP server"
    except Exception as error:
        result["connection"] = "CHECK_FAILED"
        result["connection_error"] = str(error)
    finally:
        if client is not None:
            try:
                client.unbind()
            except Exception:
                pass
            try:
                client.disconnect()
            except Exception:
                pass
    return result
