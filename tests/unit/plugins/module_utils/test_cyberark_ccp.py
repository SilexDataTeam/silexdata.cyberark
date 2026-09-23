# SPDX-FileCopyrightText: Silex Data Solutions
# SPDX-License-Identifier: Apache-2.0
#
# Tests only the Apache-2.0 module_utils, and imports no GPL plugin code, so
# this file is Apache-2.0 too.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import importlib.util
import os
import sys
from urllib.parse import parse_qs, urlsplit

import pytest
import requests
from ansible_collections.silexdata.cyberark.plugins.module_utils import cyberark_ccp
from ansible_collections.silexdata.cyberark.plugins.module_utils.cyberark_ccp import (
    CyberarkCCPError,
    ccp_argument_spec,
    cert_files,
    fetch_pas_object,
    resolve_object_property,
)

CERT = "-----BEGIN CERTIFICATE-----\ncert\n-----END CERTIFICATE-----\n"
KEY = "-----BEGIN PRIVATE KEY-----\nkey\n-----END PRIVATE KEY-----\n"


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text="", bad_json=False):
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self.text = text
        self._payload = payload
        self._bad_json = bad_json

    def json(self):
        if self._bad_json:
            raise ValueError("Expecting value: line 1 column 1 (char 0)")
        return self._payload


def _raise(exc):
    raise exc


@pytest.fixture
def fake_get(monkeypatch):
    """Replace requests.get; record each call and answer with `fake_get.response`,
    or raise `fake_get.error` when that is set."""
    calls = []

    def get(url, **kwargs):
        cert = kwargs.get("cert")
        paths = cert if isinstance(cert, tuple) else (cert,) if cert else ()
        # Snapshot the cert files while they exist: they are deleted afterwards.
        kwargs["cert_contents"] = [open(p).read() for p in paths]
        calls.append((url, kwargs))
        if get.error is not None:
            # Through a helper: pylint would infer get.error as always None.
            _raise(get.error)
        return get.response

    get.response = FakeResponse(payload={"Content": "s3cret", "UserName": "svc", "Address": "db1"})
    get.error = None
    get.calls = calls
    monkeypatch.setattr(cyberark_ccp.requests, "get", get)
    return get


def fetch(**overrides):
    kwargs = dict(url="https://cyberark.example.com", app_id="MyApp", object_query="Safe=S;Object=O")
    kwargs.update(overrides)
    return fetch_pas_object(**kwargs)


# ccp_argument_spec


def test_argument_spec_hides_every_credential():
    spec = ccp_argument_spec()
    assert {k for k, v in spec.items() if v.get("no_log")} == {"app_id", "client_cert", "client_key", "reason"}
    assert spec["url"]["required"] and spec["app_id"]["required"]
    assert spec["object_query_format"]["choices"] == ["Exact", "Regexp"]


# resolve_object_property


@pytest.mark.parametrize(
    ("given", "key"),
    [
        ("", "Content"),
        ("password", "Content"),
        ("PASSWORD", "Content"),
        ("username", "UserName"),
        ("UserName", "UserName"),
        ("address", "Address"),
        ("customField", "Customfield"),
    ],
)
def test_property_names_map_to_ccp_response_keys(given, key):
    assert resolve_object_property(given) == key


# cert_files


def test_no_cert_or_key_yields_none():
    with cert_files(None, None) as cert:
        assert cert is None


def test_a_cert_alone_is_written_to_a_file_that_is_removed_afterwards():
    with cert_files(CERT, None) as cert:
        assert isinstance(cert, str)
        with open(cert) as fh:
            assert fh.read() == CERT
    assert not os.path.exists(cert)


def test_a_cert_and_key_yield_both_paths_and_both_are_removed():
    with cert_files(CERT, KEY) as cert:
        cert_path, key_path = cert
        with open(cert_path) as fh:
            assert fh.read() == CERT
        with open(key_path) as fh:
            assert fh.read() == KEY
    assert not os.path.exists(cert_path)
    assert not os.path.exists(key_path)


def test_a_key_without_a_cert_is_never_written(monkeypatch):
    written = []
    real_mkstemp = cyberark_ccp.tempfile.mkstemp

    def mkstemp():
        fd, path = real_mkstemp()
        written.append(path)
        return fd, path

    monkeypatch.setattr(cyberark_ccp.tempfile, "mkstemp", mkstemp)
    with cert_files(None, KEY) as cert:
        assert cert is None
    assert written == []


def test_a_temp_file_already_gone_does_not_break_cleanup():
    with cert_files(CERT, KEY) as (cert_path, key_path):
        os.unlink(cert_path)
    assert not os.path.exists(key_path)


def test_temp_files_are_removed_when_the_body_raises():
    with pytest.raises(RuntimeError), cert_files(CERT, KEY) as (cert_path, key_path):
        raise RuntimeError("request failed")
    assert not os.path.exists(cert_path)
    assert not os.path.exists(key_path)


# fetch_pas_object: the request


def test_the_request_targets_the_default_web_service(fake_get):
    assert fetch() == "s3cret"
    ((url, kwargs),) = fake_get.calls
    parts = urlsplit(url)
    assert f"{parts.scheme}://{parts.netloc}{parts.path}" == "https://cyberark.example.com/AIMWebService/api/Accounts"
    assert parse_qs(parts.query) == {"AppId": ["MyApp"], "Query": ["Safe=S;Object=O"], "QueryFormat": ["Exact"]}
    assert kwargs["timeout"] == 30
    assert kwargs["verify"] is True
    assert kwargs["allow_redirects"] is False
    assert kwargs["cert"] is None


def test_query_values_are_percent_encoded(fake_get):
    fetch(object_query="Safe=My Safe;Object=a/b")
    url = fake_get.calls[0][0]
    assert "Query=Safe%3DMy%20Safe%3BObject%3Da%2Fb" in url
    assert "+" not in urlsplit(url).query


def test_optional_parameters_are_passed_through(fake_get):
    fetch(
        webservice_id="CustomWS",
        object_query_format="Regexp",
        reason="ticket 42",
        verify=False,
        timeout=5,
    )
    url, kwargs = fake_get.calls[0]
    parts = urlsplit(url)
    assert parts.path == "/CustomWS/api/Accounts"
    query = parse_qs(parts.query)
    assert query["QueryFormat"] == ["Regexp"]
    assert query["reason"] == ["ticket 42"]
    assert kwargs["verify"] is False
    assert kwargs["timeout"] == 5


def test_no_reason_means_no_reason_parameter(fake_get):
    fetch()
    assert "reason" not in parse_qs(urlsplit(fake_get.calls[0][0]).query)


def test_a_cert_bundling_its_key_is_sent_as_one_file(fake_get):
    fetch(client_cert=CERT + KEY)
    kwargs = fake_get.calls[0][1]
    assert isinstance(kwargs["cert"], str)
    assert kwargs["cert_contents"] == [CERT + KEY]
    assert not os.path.exists(kwargs["cert"])


def test_a_key_without_a_cert_is_rejected_before_any_request(fake_get):
    with pytest.raises(CyberarkCCPError, match="client_key was given without client_cert"):
        fetch(client_key=KEY)
    assert fake_get.calls == []


def test_client_certificates_are_sent_and_cleaned_up(fake_get):
    fetch(client_cert=CERT, client_key=KEY)
    kwargs = fake_get.calls[0][1]
    assert isinstance(kwargs["cert"], tuple)
    assert kwargs["cert_contents"] == [CERT, KEY]
    assert not any(os.path.exists(p) for p in kwargs["cert"])


# fetch_pas_object: the response


@pytest.mark.parametrize(
    ("object_property", "value"),
    [("", "s3cret"), ("Password", "s3cret"), ("username", "svc"), ("Address", "db1")],
)
def test_the_requested_property_is_returned(fake_get, object_property, value):
    assert fetch(object_property=object_property) == value


def test_a_property_missing_from_the_object_is_an_error(fake_get):
    with pytest.raises(CyberarkCCPError, match="'Folder' not found"):
        fetch(object_property="Folder")


def test_an_http_error_reports_status_and_body(fake_get):
    fake_get.response = FakeResponse(status_code=404, text="APPAP004E Password object matching query not found")
    with pytest.raises(CyberarkCCPError, match="HTTP 404: APPAP004E"):
        fetch()


def test_a_redirect_is_not_followed_and_is_an_error(fake_get):
    fake_get.response = FakeResponse(status_code=302, text="")
    with pytest.raises(CyberarkCCPError, match="HTTP 302"):
        fetch()


def test_a_body_that_is_not_json_is_an_error_chained_to_its_cause(fake_get):
    fake_get.response = FakeResponse(bad_json=True)
    with pytest.raises(CyberarkCCPError, match="as JSON") as excinfo:
        fetch()
    assert isinstance(excinfo.value.__cause__, ValueError)


def test_a_transport_failure_is_an_error_chained_to_its_cause(fake_get):
    fake_get.error = requests.exceptions.ConnectionError("connection refused")
    with pytest.raises(CyberarkCCPError, match="connection refused") as excinfo:
        fetch()
    assert isinstance(excinfo.value.__cause__, requests.exceptions.ConnectionError)


def test_a_transport_failure_still_removes_the_cert_files(fake_get):
    fake_get.error = requests.exceptions.SSLError("bad certificate")
    with pytest.raises(CyberarkCCPError):
        fetch(client_cert=CERT, client_key=KEY)
    assert not any(os.path.exists(p) for p in fake_get.calls[0][1]["cert"])


def test_without_requests_nothing_is_attempted(fake_get, monkeypatch):
    monkeypatch.setattr(cyberark_ccp, "HAS_REQUESTS", False)
    with pytest.raises(CyberarkCCPError, match='"requests" library is required'):
        fetch()
    assert fake_get.calls == []


def test_requests_is_optional_at_import_time(monkeypatch):
    # Load a private copy with requests hidden. Reloading the real module
    # instead would replace CyberarkCCPError and break the other tests.
    monkeypatch.setitem(sys.modules, "requests", None)
    spec = importlib.util.spec_from_file_location("cyberark_ccp_without_requests", cyberark_ccp.__file__)
    without_requests = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(without_requests)
    assert without_requests.HAS_REQUESTS is False
    with pytest.raises(without_requests.CyberarkCCPError, match='"requests" library is required'):
        without_requests.fetch_pas_object(url="https://cyberark.example.com", app_id="a", object_query="q")
