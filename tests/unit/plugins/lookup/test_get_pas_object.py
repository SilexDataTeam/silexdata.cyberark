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
    "verify": True,
    "object_query_format": "Exact",
    "object_property": "",
    "reason": None,
}


def make_lookup(options=None):
    """Build a LookupModule instance with set_options/get_option stubbed out.

    The real LookupBase.set_options()/get_option() machinery resolves the
    argument spec via the plugin's DOCUMENTATION (merged with the
    cyberark_ccp doc fragment) through the Ansible plugin loader. That is
    exercised end-to-end by ansible-test integration; here we stub it so the
    unit test can focus on LookupModule.run()'s own logic.
    """
    resolved = dict(DEFAULT_OPTIONS)
    resolved.update(options or {})

    lookup = get_pas_object.LookupModule()
    lookup.set_options = MagicMock()
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
