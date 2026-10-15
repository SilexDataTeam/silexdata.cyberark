# Copyright (c) 2026, Silex Data Solutions <info@silexdata.com>
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-FileCopyrightText: 2026 Silex Data Solutions <info@silexdata.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import sys

if sys.version_info < (3, 3):
    from mock import MagicMock, patch
else:
    from unittest.mock import MagicMock, patch

import pytest
from ansible.errors import AnsibleLookupError
from ansible_collections.silexdata.cyberark.plugins.lookup import get_pas_object
from ansible_collections.silexdata.cyberark.plugins.module_utils.cyberark_ccp import (
    CyberarkCCPError,
)

DEFAULT_OPTIONS = {
    "url": "https://cyberark.example.com",
    "app_id": "MyApp",
    "webservice_id": "",
    "client_cert": None,
    "client_key": None,
    "client_cert_file": None,
    "client_key_file": None,
    "verify": True,
    "object_query_format": "Exact",
    "object_property": "",
    "reason": None,
}


class FakeTemplar:
    """Stand-in for the lookup's Templar: renders "{{ name }}" from its variables."""

    def __init__(self, variables=None):
        self.variables = variables or {}

    def template(self, value):
        if isinstance(value, str) and value.startswith("{{ ") and value.endswith(" }}"):
            return self.variables[value[3:-3]]
        return value


def make_lookup(options=None, variables=None):
    """Build a LookupModule instance with set_options/get_option stubbed out.

    The real LookupBase.set_options()/get_option() machinery resolves the
    argument spec via the plugin's DOCUMENTATION (merged with the
    cyberark_ccp doc fragment) through the Ansible plugin loader. That is
    exercised end-to-end by ansible-test integration; here we stub it so the
    unit test can focus on LookupModule.run()'s own logic. The stub applies the
    direct options run() passes it over `options`, as the real one would.
    """
    resolved = dict(DEFAULT_OPTIONS)
    resolved.update(options or {})

    lookup = get_pas_object.LookupModule()
    lookup._templar = FakeTemplar(variables)
    lookup.set_options = MagicMock(side_effect=lambda var_options=None, direct=None: resolved.update(direct or {}))
    lookup.get_option = MagicMock(side_effect=lambda name: resolved[name])
    return lookup


@patch.object(get_pas_object, "fetch_pas_object")
def test_run_single_term_returns_single_value_list(mock_fetch):
    mock_fetch.return_value = "MySecretPassword"
    lookup = make_lookup()

    result = lookup.run(["Safe=MySafe;Object=MyAccount"], variables={})

    assert result == ["MySecretPassword"]
    mock_fetch.assert_called_once()


@patch.object(get_pas_object, "fetch_pas_object")
def test_run_multiple_terms_returns_multiple_values(mock_fetch):
    mock_fetch.side_effect = ["password-one", "password-two"]
    lookup = make_lookup()

    result = lookup.run(["Safe=A;Object=One", "Safe=A;Object=Two"], variables={})

    assert result == ["password-one", "password-two"]
    assert mock_fetch.call_count == 2


@patch.object(get_pas_object, "fetch_pas_object")
def test_run_passes_resolved_options_through(mock_fetch):
    mock_fetch.return_value = "value"
    lookup = make_lookup(
        {
            "object_query_format": "Regexp",
            "object_property": "Username",
            "client_cert": "cert-pem",
            "client_key": "key-pem",
        }
    )

    lookup.run(["Safe=MySafe;Object=MyAccount.*"], variables={})

    mock_fetch.assert_called_once_with(
        url=DEFAULT_OPTIONS["url"],
        app_id=DEFAULT_OPTIONS["app_id"],
        object_query="Safe=MySafe;Object=MyAccount.*",
        webservice_id=DEFAULT_OPTIONS["webservice_id"],
        client_cert="cert-pem",
        client_key="key-pem",
        client_cert_file=None,
        client_key_file=None,
        verify=DEFAULT_OPTIONS["verify"],
        object_query_format="Regexp",
        object_property="Username",
        reason=None,
    )


@patch.object(get_pas_object, "fetch_pas_object")
def test_run_raises_ansible_lookup_error_on_ccp_error(mock_fetch):
    """A CyberarkCCPError (e.g. missing "requests", transport failure) must
    surface as an AnsibleLookupError, not leak the raw exception type."""
    mock_fetch.side_effect = CyberarkCCPError('The Python "requests" library is required for this operation.')
    lookup = make_lookup()

    with pytest.raises(AnsibleLookupError) as exc_info:
        lookup.run(["Safe=MySafe;Object=MyAccount"], variables={})

    assert "requests" in str(exc_info.value)


@patch.object(get_pas_object, "fetch_pas_object")
def test_run_stops_at_first_error_among_multiple_terms(mock_fetch):
    mock_fetch.side_effect = ["password-one", CyberarkCCPError("boom")]
    lookup = make_lookup()

    with pytest.raises(AnsibleLookupError):
        lookup.run(["Safe=A;Object=One", "Safe=A;Object=Two"], variables={})


def test_run_rejects_a_client_key_without_a_client_cert():
    """The lookup has no argument-spec dependency check, so the shared client's
    guard is what stops it: it must surface as an AnsibleLookupError."""
    lookup = make_lookup({"client_key": "key-pem"})

    with pytest.raises(AnsibleLookupError, match="client_key was given without client_cert"):
        lookup.run(["Safe=MySafe;Object=MyAccount"], variables={})


# Fallbacks to variables and environment variables


@patch.object(get_pas_object, "fetch_pas_object")
def test_run_falls_back_to_rendered_variables_then_the_environment(mock_fetch, monkeypatch):
    mock_fetch.return_value = "value"
    monkeypatch.setenv("CYBERARK_CCP_URL", "https://env.example.com")
    monkeypatch.setenv("CYBERARK_CCP_APP_ID", "EnvApp")
    variables = {"cyberark_ccp_url": "{{ ccp }}", "ccp": "https://var.example.com"}
    lookup = make_lookup({"url": None, "app_id": None}, variables=variables)

    lookup.run(["Safe=S;Object=O"], variables=variables)

    kwargs = mock_fetch.call_args.kwargs
    assert kwargs["url"] == "https://var.example.com"
    assert kwargs["app_id"] == "EnvApp"


@patch.object(get_pas_object, "fetch_pas_object")
def test_run_passes_keyword_options_over_the_fallbacks(mock_fetch, monkeypatch):
    mock_fetch.return_value = "value"
    monkeypatch.setenv("CYBERARK_CCP_URL", "https://env.example.com")
    lookup = make_lookup({"url": None})

    lookup.run(["Safe=S;Object=O"], variables={"cyberark_ccp_url": "https://var.example.com"}, url="https://kwarg.example.com")

    assert mock_fetch.call_args.kwargs["url"] == "https://kwarg.example.com"


@patch.object(get_pas_object, "fetch_pas_object")
def test_run_hands_resolved_and_other_options_to_set_options(mock_fetch, monkeypatch):
    mock_fetch.return_value = "value"
    monkeypatch.setenv("CYBERARK_CCP_CLIENT_CERT_FILE", "/env/cert.pem")
    lookup = make_lookup()

    lookup.run(["Safe=S;Object=O"], variables={}, object_property="Username", webservice_id="")

    lookup.set_options.assert_called_once_with(
        var_options={},
        direct={"object_property": "Username", "client_cert_file": "/env/cert.pem"},
    )


def test_run_rejects_conflicting_fallbacks_as_a_lookup_error(monkeypatch):
    monkeypatch.setenv("CYBERARK_CCP_CLIENT_KEY", "key-pem")
    monkeypatch.setenv("CYBERARK_CCP_CLIENT_KEY_FILE", "/env/key.pem")
    lookup = make_lookup()

    with pytest.raises(AnsibleLookupError, match="CYBERARK_CCP_CLIENT_KEY and CYBERARK_CCP_CLIENT_KEY_FILE are mutually exclusive"):
        lookup.run(["Safe=S;Object=O"], variables={})
