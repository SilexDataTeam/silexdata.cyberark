# Copyright (c) 2026, Silex Data Solutions <info@silexdata.com>
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-FileCopyrightText: 2026 Silex Data Solutions <info@silexdata.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
name: get_pas_object
short_description: Retrieve a credential from CyberArk Central Credential Provider (CCP)
version_added: "1.0.0"
description:
  - Fetches one or more stored account objects from CyberArk's Central Credential
    Provider (CCP) via the AIM Web Service REST API.
  - Adapted from the AWX/AAP CyberArk AIM credential plugin.
  - Also available as the M(silexdata.cyberark.get_pas_object) module for use as a
    task whose result can be registered.
extends_documentation_fragment:
  - silexdata.cyberark.cyberark_ccp
options:
  _terms:
    description:
      - One or more queries used to identify the target object(s).
      - "Example: C(Safe=MySafe;Object=MyAccount)"
    required: true
    type: list
    elements: str
author:
  - Silex Data Solutions (@SilexDataTeam)
'''

EXAMPLES = r'''
---
- name: Retrieve a password from CyberArk CCP
  ansible.builtin.debug:
    msg: >-
      {{ lookup('silexdata.cyberark.get_pas_object', 'Safe=MySafe;Object=MyAccount',
         url='https://cyberark.example.com', app_id='MyApp') }}

- name: Retrieve a username using regexp query and client cert auth
  ansible.builtin.set_fact:
    my_username: >-
      {{ lookup('silexdata.cyberark.get_pas_object', 'Safe=MySafe;Object=MyAccount.*',
         url='https://cyberark.example.com',
         app_id='MyApp',
         object_query_format='Regexp',
         object_property='Username',
         client_cert=lookup('file', '/etc/ssl/client.crt'),
         client_key=lookup('file', '/etc/ssl/client.key')) }}

- name: Retrieve multiple passwords in one lookup call
  ansible.builtin.debug:
    msg: "{{ query('silexdata.cyberark.get_pas_object', 'Safe=A;Object=One', 'Safe=A;Object=Two', url=url, app_id=app_id) }}"
'''

RETURN = r'''
---
_raw:
  description: The requested property value(s) from the matched CyberArk object(s), one per term.
  type: list
  elements: str
'''

from ansible.errors import AnsibleLookupError
from ansible.plugins.lookup import LookupBase
from ansible_collections.silexdata.cyberark.plugins.module_utils.cyberark_ccp import (
    CyberarkCCPError,
    fetch_pas_object,
)


class LookupModule(LookupBase):
    def run(self, terms, variables=None, **kwargs):
        self.set_options(var_options=variables, direct=kwargs)

        url = self.get_option('url')
        app_id = self.get_option('app_id')
        webservice_id = self.get_option('webservice_id')
        client_cert = self.get_option('client_cert')
        client_key = self.get_option('client_key')
        verify = self.get_option('verify')
        object_query_format = self.get_option('object_query_format')
        object_property = self.get_option('object_property')
        reason = self.get_option('reason')

        ret = []
        for term in terms:
            try:
                value = fetch_pas_object(
                    url=url,
                    app_id=app_id,
                    object_query=term,
                    webservice_id=webservice_id,
                    client_cert=client_cert,
                    client_key=client_key,
                    verify=verify,
                    object_query_format=object_query_format,
                    object_property=object_property,
                    reason=reason,
                )
            except CyberarkCCPError as exc:
                raise AnsibleLookupError(str(exc)) from exc

            ret.append(value)

        return ret
