# Copyright (c) 2026, Silex Data Solutions <info@silexdata.com>
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-FileCopyrightText: 2026 Silex Data Solutions <info@silexdata.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible.plugins.action import ActionBase
from ansible_collections.silexdata.cyberark.plugins.module_utils.cyberark_ccp import (
    CyberarkCCPError,
    ccp_argument_spec,
    fetch_pas_object,
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

        argument_spec = ccp_argument_spec()
        argument_spec['object_query'] = dict(type='str', required=True, no_log=True)
        # Raises AnsibleActionFail, which fails the task, on invalid arguments.
        # A key without its certificate cannot authenticate.
        dummy, args = self.validate_argument_spec(
            argument_spec=argument_spec,
            required_by={'client_key': 'client_cert'},
        )

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
