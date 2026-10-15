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
      - Base URL of the CyberArk CCP endpoint (e.g. V(https://cyberark.example.com)).
      - If not set, the C(cyberark_ccp_url) variable is used, then the E(CYBERARK_CCP_URL) environment variable.
    required: true
    type: str
  app_id:
    description:
      - The Application ID registered in CyberArk for this caller.
      - If not set, the C(cyberark_ccp_app_id) variable is used, then the E(CYBERARK_CCP_APP_ID) environment variable.
    required: true
    type: str
  webservice_id:
    description:
      - The CCP Web Service ID.
      - Defaults to V(AIMWebService) when omitted or set to an empty string.
      - If not set, the C(cyberark_ccp_webservice_id) variable is used, then the E(CYBERARK_CCP_WEBSERVICE_ID) environment variable.
    required: false
    type: str
    default: ''
  client_cert:
    description:
      - PEM-encoded client certificate used for mutual TLS authentication.
      - It may also contain the matching private key, in which case O(client_key)
        is not needed.
      - Mutually exclusive with O(client_cert_file).
      - If not set, the C(cyberark_ccp_client_cert) variable is used, then the E(CYBERARK_CCP_CLIENT_CERT) environment variable,
        subject to how the client certificate and key are resolved together (see the notes).
    required: false
    type: str
  client_cert_file:
    description:
      - Path, on the controller, of a PEM file holding the client certificate used for mutual TLS authentication.
      - Like O(client_cert), the file may also contain the matching private key.
      - Mutually exclusive with O(client_cert).
      - If not set, the C(cyberark_ccp_client_cert_file) variable is used, then the E(CYBERARK_CCP_CLIENT_CERT_FILE) environment variable,
        subject to how the client certificate and key are resolved together (see the notes).
    required: false
    type: path
    version_added: 1.1.0
  client_key:
    description:
      - PEM-encoded private key matching O(client_cert) or O(client_cert_file).
      - Requires O(client_cert) or O(client_cert_file). A key on its own is rejected, since without a
        certificate there is nothing to authenticate with.
      - The key must not be encrypted.
      - Mutually exclusive with O(client_key_file).
      - If not set, the C(cyberark_ccp_client_key) variable is used, then the E(CYBERARK_CCP_CLIENT_KEY) environment variable,
        subject to how the client certificate and key are resolved together (see the notes).
    required: false
    type: str
  client_key_file:
    description:
      - Path, on the controller, of a PEM file holding the private key matching O(client_cert) or O(client_cert_file).
      - Requires O(client_cert) or O(client_cert_file), and the key must not be encrypted, as for O(client_key).
      - Mutually exclusive with O(client_key).
      - If not set, the C(cyberark_ccp_client_key_file) variable is used, then the E(CYBERARK_CCP_CLIENT_KEY_FILE) environment variable,
        subject to how the client certificate and key are resolved together (see the notes).
    required: false
    type: path
    version_added: 1.1.0
  verify:
    description:
      - Whether to verify the server's TLS certificate.
      - If not set, the C(cyberark_ccp_verify) variable is used, then the E(CYBERARK_CCP_VERIFY) environment variable.
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
notes:
  - The connection options O(url), O(app_id), O(webservice_id), O(verify), O(client_cert), O(client_cert_file),
    O(client_key) and O(client_key_file) can each be left unset and supplied instead by an Ansible variable or an
    environment variable, named in each option's description. An option set directly wins, then the variable, then
    the environment variable, which is the order Ansible applies to plugin options. A value that is unset or an empty
    string counts as not set, at every level.
  - Variables may be templated; they are rendered before use. Environment variables are read on the controller, where
    both the module and the lookup plugin run.
  - The client certificate and key are resolved together. O(client_cert), O(client_cert_file), O(client_key) and
    O(client_key_file) all come from the first of those three sources that sets any of them, so a key is never paired
    with a certificate from another source.
requirements:
  - requests >= 2.0
'''
