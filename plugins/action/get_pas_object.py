# Copyright (c) 2026, Silex Data Solutions <info@silexdata.com>
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-FileCopyrightText: 2026 Silex Data Solutions <info@silexdata.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import os

from ansible.errors import AnsibleActionFail
from ansible.module_utils.common.arg_spec import ArgumentSpecValidator
from ansible.module_utils.errors import UnsupportedError
from ansible.plugins.action import ActionBase
from ansible_collections.silexdata.cyberark.plugins.module_utils.cyberark_ccp import (
    FALLBACK_OPTIONS,
    CyberarkCCPError,
    ccp_argument_spec,
    fetch_pas_object,
    resolve_fallbacks,
)


class ActionModule(ActionBase):
    """Retrieve a credential from CyberArk CCP on the controller.

    Nothing runs on the managed node: the request is made from the controller,
    like the lookup plugin's, so only the controller needs "requests" and
    network access to CCP. The task's host only receives the registered result.
    """

    TRANSFERS_FILES = False
    _requires_connection = False
    _supports_check_mode = True
    _supports_async = False

    def run(self, tmp=None, task_vars=None):
        result = super().run(tmp, task_vars)
        del tmp

        # Raises AnsibleActionFail, which fails the task, on invalid arguments.
        args = self._resolve_args(task_vars)

        if self._task.check_mode:
            # Read-only, so there is never a change to predict; skipping the
            # request means a playbook can be validated without CCP access.
            result.update(changed=False, value=None)
            return result

        try:
            value = fetch_pas_object(
                url=args['url'],
                app_id=args['app_id'],
                object_query=args['object_query'],
                webservice_id=args['webservice_id'],
                client_cert=args['client_cert'],
                client_key=args['client_key'],
                client_cert_file=args['client_cert_file'],
                client_key_file=args['client_key_file'],
                verify=args['verify'],
                object_query_format=args['object_query_format'],
                object_property=args['object_property'],
                reason=args['reason'],
            )
        except CyberarkCCPError as exc:
            result.update(failed=True, msg=str(exc))
            return result

        result.update(changed=False, value=value)
        return result

    def _resolve_args(self, task_vars):
        """Return the validated task arguments, with unset connection options filled from variables or the environment.

        Like ActionBase.validate_argument_spec, but over the resolved arguments
        rather than the task's own, so a value from a variable or environment
        variable is checked and converted exactly as an argument would be.
        """
        try:
            resolved = resolve_fallbacks(self._task.args, task_vars, os.environ, self._templar.template)
        except CyberarkCCPError as exc:
            raise AnsibleActionFail(str(exc)) from exc

        params = {name: value for name, value in self._task.args.items() if name not in FALLBACK_OPTIONS}
        params.update(resolved)

        argument_spec = ccp_argument_spec()
        argument_spec['object_query'] = dict(type='str', required=True, no_log=True)
        validation = ArgumentSpecValidator(argument_spec).validate(params)
        if validation.error_messages:
            msg = validation.errors.msg
            if isinstance(validation.errors[0], UnsupportedError):
                msg = f'Unsupported parameters for ({self._task.action}) module: {msg}'
            raise AnsibleActionFail(msg)

        return validation.validated_parameters
