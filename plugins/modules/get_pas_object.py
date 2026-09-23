#!/usr/bin/python

# Copyright (c) 2026, Silex Data Solutions <info@silexdata.com>
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-FileCopyrightText: 2026 Silex Data Solutions <info@silexdata.com>
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: get_pas_object
short_description: Retrieve a credential from CyberArk Central Credential Provider (CCP)
version_added: "1.0.0"
description:
  - Fetches a stored account object from CyberArk's Central Credential Provider (CCP)
    via the AIM Web Service REST API.
  - Adapted from the AWX/AAP CyberArk AIM credential plugin.
  - Also available as the M(silexdata.cyberark.get_pas_object) lookup plugin for use
    directly in templates without registering a task result.
  - Runs on the controller, whichever host the task targets, so only the controller needs the
    Python C(requests) library and network access to CCP. The result is registered on the task's host.
  - In check mode, no request is made to CyberArk CCP; RV(value) is returned as V(none).
extends_documentation_fragment:
  - silexdata.cyberark.cyberark_ccp
  - ansible.builtin.action_common_attributes
  - ansible.builtin.action_common_attributes.flow
attributes:
  action:
    support: full
  async:
    support: none
  bypass_host_loop:
    support: none
  check_mode:
    support: full
    details: No request is made to CyberArk CCP, and RV(value) is returned as V(none).
  diff_mode:
    support: none
  platform:
    platforms: all
options:
  object_query:
    description:
      - Query used to identify the target object.
      - "Example: C(Safe=MySafe;Object=MyAccount)"
    required: true
    type: str
author:
  - Silex Data Solutions (@SilexDataTeam)
'''

EXAMPLES = r'''
---
- name: Retrieve a password from CyberArk CCP
  silexdata.cyberark.get_pas_object:
    url: https://cyberark.example.com
    app_id: MyApp
    object_query: "Safe=MySafe;Object=MyAccount"
  register: result
  no_log: true

- name: Retrieve a username using regexp query and client cert auth
  silexdata.cyberark.get_pas_object:
    url: https://cyberark.example.com
    app_id: MyApp
    object_query: "Safe=MySafe;Object=MyAccount.*"
    object_query_format: Regexp
    object_property: Username
    client_cert: "{{ lookup('file', '/etc/ssl/client.crt') }}"
    client_key: "{{ lookup('file', '/etc/ssl/client.key') }}"
  register: result
  no_log: true
'''

RETURN = r'''
---
value:
  description: The requested property value from the CyberArk object. C(none) in check mode.
  returned: success
  type: str
  sample: "MySecretPassword"
'''
