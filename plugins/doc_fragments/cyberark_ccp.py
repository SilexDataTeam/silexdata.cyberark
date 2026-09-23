# Copyright (c) 2026, Silex Data Solutions <info@silexdata.com>
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-FileCopyrightText: 2026 Silex Data Solutions <info@silexdata.com>
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Option documentation adapted from AWX (awx/main/credential_plugins/aim.py, Apache-2.0).

from __future__ import absolute_import, division, print_function

__metaclass__ = type


class ModuleDocFragment:
    # Options shared by every plugin that talks to CyberArk's Central
    # Credential Provider (CCP) via the AIM Web Service REST API.
    DOCUMENTATION = r'''
---
options:
  url:
    description:
      - Base URL of the CyberArk CCP endpoint (e.g. C(https://cyberark.example.com)).
    required: true
    type: str
  app_id:
    description:
      - The Application ID registered in CyberArk for this caller.
    required: true
    type: str
  webservice_id:
    description:
      - The CCP Web Service ID.
      - Defaults to C(AIMWebService) when omitted or set to an empty string.
    required: false
    type: str
    default: ''
  client_cert:
    description:
      - PEM-encoded client certificate used for mutual TLS authentication.
      - It may also contain the matching private key, in which case O(client_key)
        is not needed.
    required: false
    type: str
  client_key:
    description:
      - PEM-encoded private key matching O(client_cert).
      - Requires O(client_cert). A key on its own is rejected, since without a
        certificate there is nothing to authenticate with.
    required: false
    type: str
  verify:
    description:
      - Whether to verify the server's TLS certificate.
    required: false
    type: bool
    default: true
  object_query_format:
    description:
      - The format of the query used to identify the target object (the
        C(object_query) module parameter, or C(_terms) for the lookup plugin).
    required: false
    type: str
    default: Exact
    choices: [Exact, Regexp]
  object_property:
    description:
      - The property of the matched object to return.
      - C(Password) and an empty string both return the credential secret (C(Content) in the CCP response).
      - C(Username) returns the account username.
      - C(Address) returns the account address.
    required: false
    type: str
    default: ''
  reason:
    description:
      - The reason for the credential retrieval request.
      - Only required when the object's CyberArk policy mandates a reason.
    required: false
    type: str
requirements:
  - requests >= 2.0
'''
