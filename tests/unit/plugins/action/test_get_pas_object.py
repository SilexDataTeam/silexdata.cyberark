# Copyright (c) 2026, Silex Data Solutions <info@silexdata.com>
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-FileCopyrightText: 2026 Silex Data Solutions <info@silexdata.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from unittest.mock import MagicMock, patch

import pytest
from ansible.errors import AnsibleActionFail
from ansible.playbook.task import Task
from ansible_collections.silexdata.cyberark.plugins.action import get_pas_object
from ansible_collections.silexdata.cyberark.plugins.module_utils.cyberark_ccp import (
    CyberarkCCPError,
)

BASE_ARGS = {
    "url": "https://cyberark.example.com",
    "app_id": "MyApp",
    "object_query": "Safe=MySafe;Object=MyAccount",
}


class FakeTemplar:
    """Stand-in for the task's Templar: renders "{{ name }}" from its variables."""

    def __init__(self, variables=None):
        self.variables = variables or {}

    def template(self, value):
        if isinstance(value, str) and value.startswith("{{ ") and value.endswith(" }}"):
            return self.variables[value[3:-3]]
        return value


def make_action(args, check_mode=False, templar=None):
    task = MagicMock(Task)
    task.action = "silexdata.cyberark.get_pas_object"
    task.args = dict(args)
    task.check_mode = check_mode
    task.async_val = 0
    task.diff = False
    connection = MagicMock()
    action = get_pas_object.ActionModule(
        task=task,
        connection=connection,
        play_context=MagicMock(),
        loader=None,
        templar=templar or FakeTemplar(),
        shared_loader_obj=None,
    )
    return action, connection


@patch.object(get_pas_object, "fetch_pas_object")
def test_the_value_is_returned_and_nothing_changes(mock_fetch):
    mock_fetch.return_value = "MySecretPassword"
    action, dummy = make_action(BASE_ARGS)

    result = action.run(task_vars={})

    assert result["changed"] is False
    assert result["value"] == "MySecretPassword"
    assert not result.get("failed")


@patch.object(get_pas_object, "fetch_pas_object")
def test_arguments_reach_the_client_with_their_defaults(mock_fetch):
    mock_fetch.return_value = "value"
    action, dummy = make_action(dict(BASE_ARGS, object_query_format="Regexp", client_cert="cert-pem"))

    action.run(task_vars={})

    mock_fetch.assert_called_once_with(
        url=BASE_ARGS["url"],
        app_id=BASE_ARGS["app_id"],
        object_query=BASE_ARGS["object_query"],
        webservice_id="",
        client_cert="cert-pem",
        client_key=None,
        client_cert_file=None,
        client_key_file=None,
        verify=True,
        object_query_format="Regexp",
        object_property="",
        reason=None,
    )


@patch.object(get_pas_object, "fetch_pas_object")
def test_nothing_touches_the_managed_node(mock_fetch):
    mock_fetch.return_value = "value"
    action, connection = make_action(BASE_ARGS)

    action.run(task_vars={})

    assert get_pas_object.ActionModule._requires_connection is False
    connection.exec_command.assert_not_called()
    connection.put_file.assert_not_called()


@patch.object(get_pas_object, "fetch_pas_object")
def test_a_ccp_error_fails_the_task(mock_fetch):
    mock_fetch.side_effect = CyberarkCCPError("CyberArk CCP returned HTTP 404: not found")
    action, dummy = make_action(BASE_ARGS)

    result = action.run(task_vars={})

    assert result["failed"] is True
    assert "404" in result["msg"]
    assert "value" not in result


@patch.object(get_pas_object, "fetch_pas_object")
def test_check_mode_returns_none_without_contacting_ccp(mock_fetch):
    action, dummy = make_action(BASE_ARGS, check_mode=True)

    result = action.run(task_vars={})

    assert result["changed"] is False
    assert result["value"] is None
    mock_fetch.assert_not_called()


@pytest.mark.parametrize("missing", ["url", "app_id", "object_query"])
@patch.object(get_pas_object, "fetch_pas_object")
def test_required_arguments_are_enforced(mock_fetch, missing):
    args = dict(BASE_ARGS)
    del args[missing]
    action, dummy = make_action(args)

    with pytest.raises(AnsibleActionFail, match=missing):
        action.run(task_vars={})
    mock_fetch.assert_not_called()


@patch.object(get_pas_object, "fetch_pas_object")
def test_a_client_key_without_a_client_cert_is_rejected(mock_fetch):
    action, dummy = make_action(dict(BASE_ARGS, client_key="key-pem"))

    with pytest.raises(AnsibleActionFail, match="client_cert"):
        action.run(task_vars={})
    mock_fetch.assert_not_called()


@patch.object(get_pas_object, "fetch_pas_object")
def test_an_unknown_query_format_is_rejected(mock_fetch):
    action, dummy = make_action(dict(BASE_ARGS, object_query_format="Glob"))

    with pytest.raises(AnsibleActionFail, match="object_query_format"):
        action.run(task_vars={})
    mock_fetch.assert_not_called()


# Fallbacks to variables and environment variables


@patch.object(get_pas_object, "fetch_pas_object")
def test_connection_settings_fall_back_to_the_environment(mock_fetch, monkeypatch):
    monkeypatch.setenv("CYBERARK_CCP_URL", "https://env.example.com")
    monkeypatch.setenv("CYBERARK_CCP_APP_ID", "EnvApp")
    monkeypatch.setenv("CYBERARK_CCP_CLIENT_CERT_FILE", "/env/cert.pem")
    monkeypatch.setenv("CYBERARK_CCP_CLIENT_KEY_FILE", "/env/key.pem")
    action, dummy = make_action({"object_query": "Safe=S;Object=O"})

    action.run(task_vars={})

    kwargs = mock_fetch.call_args.kwargs
    assert kwargs["url"] == "https://env.example.com"
    assert kwargs["app_id"] == "EnvApp"
    assert kwargs["client_cert_file"] == "/env/cert.pem"
    assert kwargs["client_key_file"] == "/env/key.pem"


@patch.object(get_pas_object, "fetch_pas_object")
def test_connection_settings_fall_back_to_rendered_variables(mock_fetch, monkeypatch):
    monkeypatch.setenv("CYBERARK_CCP_URL", "https://env.example.com")
    task_vars = {"cyberark_ccp_url": "{{ ccp }}", "cyberark_ccp_app_id": "VarApp", "ccp": "https://var.example.com"}
    action, dummy = make_action({"object_query": "Safe=S;Object=O"}, templar=FakeTemplar(task_vars))

    action.run(task_vars=task_vars)

    kwargs = mock_fetch.call_args.kwargs
    assert kwargs["url"] == "https://var.example.com"
    assert kwargs["app_id"] == "VarApp"


@patch.object(get_pas_object, "fetch_pas_object")
def test_task_arguments_win_over_variables_and_the_environment(mock_fetch, monkeypatch):
    monkeypatch.setenv("CYBERARK_CCP_URL", "https://env.example.com")
    action, dummy = make_action(BASE_ARGS)

    action.run(task_vars={"cyberark_ccp_url": "https://var.example.com"})

    assert mock_fetch.call_args.kwargs["url"] == BASE_ARGS["url"]


@pytest.mark.parametrize(("given", "verify"), [("false", False), ("False", False), ("no", False), ("true", True)])
@patch.object(get_pas_object, "fetch_pas_object")
def test_an_environment_value_is_converted_like_an_argument(mock_fetch, monkeypatch, given, verify):
    monkeypatch.setenv("CYBERARK_CCP_VERIFY", given)
    action, dummy = make_action(BASE_ARGS)

    action.run(task_vars={})

    assert mock_fetch.call_args.kwargs["verify"] is verify


@patch.object(get_pas_object, "fetch_pas_object")
def test_an_unconvertible_environment_value_is_rejected(mock_fetch, monkeypatch):
    monkeypatch.setenv("CYBERARK_CCP_VERIFY", "sometimes")
    action, dummy = make_action(BASE_ARGS)

    with pytest.raises(AnsibleActionFail, match="verify"):
        action.run(task_vars={})
    mock_fetch.assert_not_called()


@patch.object(get_pas_object, "fetch_pas_object")
def test_conflicting_environment_variables_are_rejected_by_name(mock_fetch, monkeypatch):
    monkeypatch.setenv("CYBERARK_CCP_CLIENT_CERT", "cert-pem")
    monkeypatch.setenv("CYBERARK_CCP_CLIENT_CERT_FILE", "/env/cert.pem")
    action, dummy = make_action(BASE_ARGS)

    with pytest.raises(AnsibleActionFail, match="CYBERARK_CCP_CLIENT_CERT and CYBERARK_CCP_CLIENT_CERT_FILE are mutually exclusive"):
        action.run(task_vars={})
    mock_fetch.assert_not_called()


@patch.object(get_pas_object, "fetch_pas_object")
def test_a_variable_key_without_a_variable_cert_is_rejected_even_in_check_mode(mock_fetch, monkeypatch):
    monkeypatch.setenv("CYBERARK_CCP_CLIENT_CERT", "cert-pem")
    action, dummy = make_action(BASE_ARGS, check_mode=True)

    with pytest.raises(AnsibleActionFail, match="cyberark_ccp_client_key was given without cyberark_ccp_client_cert"):
        action.run(task_vars={"cyberark_ccp_client_key": "key-pem"})
    mock_fetch.assert_not_called()


@patch.object(get_pas_object, "fetch_pas_object")
def test_check_mode_accepts_settings_from_the_environment(mock_fetch, monkeypatch):
    monkeypatch.setenv("CYBERARK_CCP_URL", "https://env.example.com")
    monkeypatch.setenv("CYBERARK_CCP_APP_ID", "EnvApp")
    action, dummy = make_action({"object_query": "Safe=S;Object=O"}, check_mode=True)

    result = action.run(task_vars={})

    assert result["value"] is None
    assert not result.get("failed")
    mock_fetch.assert_not_called()


@patch.object(get_pas_object, "fetch_pas_object")
def test_an_unknown_argument_is_rejected(mock_fetch):
    action, dummy = make_action(dict(BASE_ARGS, client_cert_flie="/typo.pem"))

    with pytest.raises(AnsibleActionFail, match="Unsupported parameters.*client_cert_flie"):
        action.run(task_vars={})
    mock_fetch.assert_not_called()
