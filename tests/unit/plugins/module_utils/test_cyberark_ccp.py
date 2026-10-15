# SPDX-FileCopyrightText: Silex Data Solutions
# SPDX-License-Identifier: Apache-2.0
#
# Tests only the Apache-2.0 module_utils, and imports no GPL plugin code, so
# this file is Apache-2.0 too.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import importlib.util
import os
import re
import sys
from urllib.parse import parse_qs, urlsplit

import pytest
import requests
from ansible_collections.silexdata.cyberark.plugins.module_utils import cyberark_ccp
from ansible_collections.silexdata.cyberark.plugins.module_utils.cyberark_ccp import (
    FALLBACK_OPTIONS,
    CyberarkCCPError,
    ccp_argument_spec,
    cert_files,
    fallback_names,
    fetch_pas_object,
    resolve_fallbacks,
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


def test_the_cert_and_key_files_are_paths():
    spec = ccp_argument_spec()
    assert spec["client_cert_file"]["type"] == spec["client_key_file"]["type"] == "path"


def test_every_fallback_option_is_in_the_argument_spec():
    assert set(FALLBACK_OPTIONS) <= set(ccp_argument_spec())


# resolve_fallbacks


def render(value):
    """Stand-in for Templar.template: renders "{{ name }}" from RENDERED."""
    if isinstance(value, str) and value.startswith("{{ ") and value.endswith(" }}"):
        return RENDERED[value[3:-3]]
    return value


RENDERED = {"ccp_host": "https://from-a-template.example.com", "blank": ""}


def var(option, value):
    return {fallback_names(option)[0]: value}


def env(option, value):
    return {fallback_names(option)[1]: value}


def resolve(direct=None, variables=None, environ=None):
    return resolve_fallbacks(direct or {}, variables, environ or {}, render)


def test_fallback_names_follow_the_option_name():
    assert fallback_names("client_cert_file") == ("cyberark_ccp_client_cert_file", "CYBERARK_CCP_CLIENT_CERT_FILE")


def test_an_option_set_directly_wins():
    resolved = resolve({"url": "direct"}, var("url", "variable"), env("url", "environment"))
    assert resolved == {"url": "direct"}


def test_a_variable_beats_the_environment():
    assert resolve({}, var("app_id", "variable"), env("app_id", "environment")) == {"app_id": "variable"}


def test_the_environment_is_the_last_resort():
    assert resolve({}, {}, env("webservice_id", "environment")) == {"webservice_id": "environment"}


def test_options_set_nowhere_are_left_out_for_their_defaults():
    assert resolve() == {}


def test_missing_variables_are_tolerated():
    assert resolve({}, None, env("url", "environment")) == {"url": "environment"}


@pytest.mark.parametrize("empty", [None, ""])
def test_an_empty_value_falls_through_to_the_next_source(empty):
    resolved = resolve({"url": empty}, var("url", empty), env("url", "environment"))
    assert resolved == {"url": "environment"}


def test_a_false_value_is_set():
    assert resolve({"verify": False}, var("verify", True)) == {"verify": False}


def test_variables_are_rendered_but_nothing_else_is():
    resolved = resolve({"app_id": "{{ ccp_host }}"}, var("url", "{{ ccp_host }}"), env("webservice_id", "{{ ccp_host }}"))
    assert resolved == {
        "url": "https://from-a-template.example.com",
        "app_id": "{{ ccp_host }}",
        "webservice_id": "{{ ccp_host }}",
    }


def test_a_variable_that_renders_empty_falls_through():
    assert resolve({}, var("url", "{{ blank }}"), env("url", "environment")) == {"url": "environment"}


def test_other_options_never_fall_back():
    environ = {"CYBERARK_CCP_REASON": "r", "CYBERARK_CCP_OBJECT_PROPERTY": "Username"}
    assert resolve({}, {"cyberark_ccp_reason": "r"}, environ) == {}


def test_the_cert_and_key_come_from_the_first_source_that_sets_either():
    variables = dict(var("client_cert_file", "/var/cert.pem"), **var("client_key_file", "/var/key.pem"))
    environ = env("client_key", "env-key")
    resolved = resolve({"client_cert": "direct-cert"}, variables, environ)
    assert resolved == {"client_cert": "direct-cert"}


def test_a_key_is_not_paired_with_a_certificate_from_another_source():
    with pytest.raises(CyberarkCCPError, match="^cyberark_ccp_client_key_file was given without cyberark_ccp_client_cert or "):
        resolve({}, var("client_key_file", "/var/key.pem"), env("client_cert", "env-cert"))


def test_a_key_given_directly_without_a_cert_names_the_options():
    with pytest.raises(CyberarkCCPError, match="^client_key was given without client_cert or client_cert_file"):
        resolve({"client_key": "key"})


@pytest.mark.parametrize(
    ("content", "path"),
    [("client_cert", "client_cert_file"), ("client_key", "client_key_file")],
)
def test_pem_content_and_a_path_from_one_source_conflict(content, path):
    environ = dict(env("client_cert", "cert"), **env(content, "pem"), **env(path, "/env/pem"))
    with pytest.raises(CyberarkCCPError, match=f"{fallback_names(content)[1]} and {fallback_names(path)[1]} are mutually exclusive"):
        resolve({}, {}, environ)


def test_the_cert_and_key_files_are_resolved_together():
    environ = dict(env("client_cert_file", "/env/cert.pem"), **env("client_key_file", "/env/key.pem"))
    assert resolve({}, {}, environ) == {"client_cert_file": "/env/cert.pem", "client_key_file": "/env/key.pem"}


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


def test_cert_and_key_paths_are_used_as_they_are_and_kept(tmp_path):
    cert_file, key_file = tmp_path / "cert.pem", tmp_path / "key.pem"
    cert_file.write_text(CERT)
    key_file.write_text(KEY)
    with cert_files(None, None, str(cert_file), str(key_file)) as cert:
        assert cert == (str(cert_file), str(key_file))
    assert cert_file.exists() and key_file.exists()


def test_cert_content_pairs_with_a_key_path(tmp_path):
    key_file = tmp_path / "key.pem"
    key_file.write_text(KEY)
    with cert_files(CERT, None, None, str(key_file)) as (cert_path, key_path):
        assert key_path == str(key_file)
        with open(cert_path) as fh:
            assert fh.read() == CERT
    assert not os.path.exists(cert_path)
    assert key_file.exists()


def test_a_key_path_without_a_cert_is_not_presented():
    with cert_files(None, None, None, "/no/cert/for/this/key.pem") as cert:
        assert cert is None


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


def test_a_key_file_without_a_cert_is_rejected_before_any_request(fake_get, tmp_path):
    key_file = tmp_path / "key.pem"
    key_file.write_text(KEY)
    with pytest.raises(CyberarkCCPError, match="client_key_file was given without client_cert or client_cert_file"):
        fetch(client_key_file=str(key_file))
    assert fake_get.calls == []


@pytest.mark.parametrize(
    ("content", "path"),
    [("client_cert", "client_cert_file"), ("client_key", "client_key_file")],
)
def test_pem_content_and_a_path_together_are_rejected(fake_get, tmp_path, content, path):
    pem_file = tmp_path / "pem"
    pem_file.write_text(CERT)
    with pytest.raises(CyberarkCCPError, match=f"{content} and {path} are mutually exclusive"):
        fetch(**{"client_cert": CERT, content: CERT, path: str(pem_file)})
    assert fake_get.calls == []


def test_cert_and_key_files_are_sent_and_kept(fake_get, tmp_path):
    cert_file, key_file = tmp_path / "cert.pem", tmp_path / "key.pem"
    cert_file.write_text(CERT)
    key_file.write_text(KEY)
    fetch(client_cert_file=str(cert_file), client_key_file=str(key_file))
    kwargs = fake_get.calls[0][1]
    assert kwargs["cert"] == (str(cert_file), str(key_file))
    assert cert_file.exists() and key_file.exists()


@pytest.mark.parametrize("option", ["client_cert_file", "client_key_file"])
def test_a_missing_file_is_rejected_before_any_request(fake_get, tmp_path, option):
    cert_file = tmp_path / "cert.pem"
    cert_file.write_text(CERT)
    missing = str(tmp_path / "missing.pem")
    args = {"client_cert_file": str(cert_file), option: missing}
    with pytest.raises(CyberarkCCPError, match=re.escape(f"{option} '{missing}' does not exist or is not a file")):
        fetch(**args)
    assert fake_get.calls == []


def test_an_empty_file_is_rejected_before_any_request(fake_get, tmp_path):
    # What an AAP file injector writes for a credential input left blank.
    empty = tmp_path / "empty.pem"
    empty.write_text("")
    with pytest.raises(CyberarkCCPError, match=re.escape(f"client_cert_file '{empty}' is empty")):
        fetch(client_cert_file=str(empty))
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
