from types import SimpleNamespace

import smpplib.consts
import smpplib.exceptions

from backend.services import sms_service


def configured(monkeypatch):
    monkeypatch.setenv("SMPP_ENABLED", "true")
    monkeypatch.setenv("SMPP_HOST", "provider.example")
    monkeypatch.setenv("SMPP_PORT", "2775")
    monkeypatch.setenv("SMPP_SYSTEM_ID", "system-id")
    monkeypatch.setenv("SMPP_PASSWORD", "secret")
    monkeypatch.setenv("SMPP_SOURCE_ADDR", "LANDNEXUS")


def test_number_normalization():
    assert sms_service.normalize_mobile_number("6379377627") == "916379377627"
    assert sms_service.normalize_mobile_number("+916379377627") == "916379377627"
    assert sms_service.normalize_mobile_number("916379377627") == "916379377627"


def test_invalid_number_does_not_connect(monkeypatch):
    configured(monkeypatch)
    client = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not connect"))
    monkeypatch.setattr(sms_service.smpplib.client, "Client", client)
    result = sms_service.send_sms("12345", "hello")
    assert result["status"] == "INVALID_DESTINATION"
    assert result["success"] is False


def test_missing_configuration(monkeypatch):
    monkeypatch.setenv("SMPP_ENABLED", "true")
    for name in ("SMPP_HOST", "SMPP_SYSTEM_ID", "SMPP_PASSWORD", "SMPP_SOURCE_ADDR"):
        monkeypatch.delenv(name, raising=False)
    result = sms_service.send_sms("6379377627", "hello")
    assert result["status"] == "SMPP_CONFIGURATION_ERROR"
    assert "SMPP_HOST" in result["error_description"]


def test_connection_failure(monkeypatch):
    configured(monkeypatch)

    class FailingClient:
        def __init__(self, *args, **kwargs):
            pass

        def connect(self):
            raise ConnectionRefusedError("refused")

    monkeypatch.setattr(sms_service.smpplib.client, "Client", FailingClient)
    result = sms_service.send_sms("6379377627", "hello")
    assert result["status"] == "SMPP_CONNECTION_FAILED"
    assert result["retryable"] is True


def test_bind_failure(monkeypatch):
    configured(monkeypatch)

    class BindFailClient:
        def __init__(self, *args, **kwargs):
            pass

        def connect(self):
            pass

        def bind_transceiver(self, **kwargs):
            raise smpplib.exceptions.PDUError("bad credentials", smpplib.consts.SMPP_ESME_RINVPASWD)

        def unbind(self):
            pass

        def disconnect(self):
            pass

    monkeypatch.setattr(sms_service.smpplib.client, "Client", BindFailClient)
    result = sms_service.send_sms("6379377627", "hello")
    assert result["status"] == "SMPP_BIND_FAILED"
    assert result["error_code"] == "SMPP_ESME_RINVPASWD"


def test_submit_success_uses_provider_message_id(monkeypatch):
    configured(monkeypatch)

    class SuccessfulClient:
        def __init__(self, *args, **kwargs):
            self.submitted = None

        def connect(self):
            pass

        def bind_transceiver(self, **kwargs):
            return SimpleNamespace(status=smpplib.consts.SMPP_ESME_ROK)

        def send_message(self, **kwargs):
            self.submitted = kwargs

        def read_pdu(self):
            return SimpleNamespace(command="submit_sm_resp", status=smpplib.consts.SMPP_ESME_ROK, message_id="provider-123")

        def unbind(self):
            pass

        def disconnect(self):
            pass

    client = SuccessfulClient()
    monkeypatch.setattr(sms_service.smpplib.client, "Client", lambda *args, **kwargs: client)
    result = sms_service.send_sms("+916379377627", "hello")
    assert result["status"] == "SUBMITTED"
    assert result["success"] is True
    assert result["message_id"] == "provider-123"
    assert client.submitted["destination_addr"] == "916379377627"


def test_submit_rejection(monkeypatch):
    configured(monkeypatch)

    class RejectedClient:
        def __init__(self, *args, **kwargs):
            pass

        def connect(self):
            pass

        def bind_transceiver(self, **kwargs):
            return SimpleNamespace(status=smpplib.consts.SMPP_ESME_ROK)

        def send_message(self, **kwargs):
            pass

        def read_pdu(self):
            return SimpleNamespace(command="submit_sm_resp", status=smpplib.consts.SMPP_ESME_RTHROTTLED, message_id=None)

        def unbind(self):
            pass

        def disconnect(self):
            pass

    monkeypatch.setattr(sms_service.smpplib.client, "Client", lambda *args, **kwargs: RejectedClient())
    result = sms_service.send_sms("6379377627", "hello")
    assert result["status"] == "SMPP_SUBMIT_FAILED"
    assert result["error_code"] == "SMPP_ESME_RTHROTTLED"
    assert result["retryable"] is True


def test_unicode_sms_uses_ucs2(monkeypatch):
    configured(monkeypatch)

    class UnicodeClient:
        def __init__(self, *args, **kwargs):
            self.submitted = None

        def connect(self):
            pass

        def bind_transceiver(self, **kwargs):
            return SimpleNamespace(status=smpplib.consts.SMPP_ESME_ROK)

        def send_message(self, **kwargs):
            self.submitted = kwargs

        def read_pdu(self):
            return SimpleNamespace(command="submit_sm_resp", status=smpplib.consts.SMPP_ESME_ROK, message_id="unicode-123")

        def unbind(self):
            pass

        def disconnect(self):
            pass

    client = UnicodeClient()
    monkeypatch.setattr(sms_service.smpplib.client, "Client", lambda *args, **kwargs: client)
    result = sms_service.send_sms("6379377627", "நில பதிவு")
    assert result["status"] == "SUBMITTED"
    assert client.submitted["data_coding"] == smpplib.consts.SMPP_ENCODING_ISO10646


def test_submit_malformed_response(monkeypatch):
    configured(monkeypatch)

    class MalformedClient:
        def __init__(self, *args, **kwargs):
            pass

        def connect(self):
            pass

        def bind_transceiver(self, **kwargs):
            return SimpleNamespace(status=smpplib.consts.SMPP_ESME_ROK)

        def send_message(self, **kwargs):
            pass

        def read_pdu(self):
            return SimpleNamespace(command="enquire_link", status=smpplib.consts.SMPP_ESME_ROK)

        def unbind(self):
            pass

        def disconnect(self):
            pass

    monkeypatch.setattr(sms_service.smpplib.client, "Client", lambda *args, **kwargs: MalformedClient())
    result = sms_service.send_sms("6379377627", "hello")
    assert result["status"] == "SMPP_SUBMIT_FAILED"
    assert result["error_code"] == "MALFORMED_RESPONSE"


def test_submit_pdu_error_and_timeout(monkeypatch):
    configured(monkeypatch)

    class SubmitErrorClient:
        def __init__(self, *args, **kwargs):
            pass

        def connect(self):
            pass

        def bind_transceiver(self, **kwargs):
            return SimpleNamespace(status=smpplib.consts.SMPP_ESME_ROK)

        def send_message(self, **kwargs):
            raise smpplib.exceptions.PDUError("submit rejected", smpplib.consts.SMPP_ESME_RSUBMITFAIL)

        def unbind(self):
            pass

        def disconnect(self):
            pass

    monkeypatch.setattr(sms_service.smpplib.client, "Client", lambda *args, **kwargs: SubmitErrorClient())
    result = sms_service.send_sms("6379377627", "hello")
    assert result["status"] == "SMPP_SUBMIT_FAILED"
    assert result["error_code"] == "SMPP_ESME_RSUBMITFAIL"

    class TimeoutClient:
        def __init__(self, *args, **kwargs):
            pass

        def connect(self):
            raise TimeoutError("timed out")

    monkeypatch.setattr(sms_service.smpplib.client, "Client", TimeoutClient)
    result = sms_service.send_sms("6379377627", "hello")
    assert result["status"] == "SMPP_CONNECTION_FAILED"
    assert result["retryable"] is True