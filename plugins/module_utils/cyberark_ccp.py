# Copyright (c) 2019 The AWX Project contributors
# Copyright (c) 2026 Silex Data Solutions <info@silexdata.com>
#
# Portions of this file are derived from the CyberArk AIM / CCP credential
# plugin of the AWX Project (originally awx/main/credential_plugins/aim.py,
# now awx-plugins/src/awx_plugins/credentials/aim.py), licensed under the
# Apache License, Version 2.0. A copy is provided in LICENSES/Apache-2.0.txt
# and at http://www.apache.org/licenses/LICENSE-2.0
# Upstream: https://github.com/ansible/awx-plugins
#
# This file has been modified from the original: it has been substantially
# reworked into a standalone Ansible module_utils helper, independent of
# Django and of the AWX credential-plugin framework.
#
# SPDX-FileCopyrightText: 2019 The AWX Project contributors
# SPDX-FileCopyrightText: 2026 Silex Data Solutions <info@silexdata.com>
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import contextlib
import os
import tempfile
from urllib.parse import quote, urlencode, urljoin

try:
    import requests

    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


def ccp_argument_spec():
    """Return the argument_spec fragment shared by every plugin that talks to CyberArk CCP.

    Kept in sync with the ``options`` documented by the C(silexdata.cyberark.cyberark_ccp)
    doc fragment (plugins/doc_fragments/cyberark_ccp.py).
    """
    return dict(
        url=dict(type='str', required=True),
        app_id=dict(type='str', required=True, no_log=True),
        webservice_id=dict(type='str', default=''),
        client_cert=dict(type='str', no_log=True),
        client_key=dict(type='str', no_log=True),
        verify=dict(type='bool', default=True),
        object_query_format=dict(type='str', default='Exact', choices=['Exact', 'Regexp']),
        object_property=dict(type='str', default=''),
        reason=dict(type='str', no_log=True),
    )


class CyberarkCCPError(Exception):
    """Raised when a CyberArk CCP request fails or its response is unusable."""


@contextlib.contextmanager
def cert_files(cert_pem, key_pem):
    """Write PEM strings to temp files and yield the requests-compatible cert argument."""
    paths = []
    try:
        cert_path = key_path = None

        if cert_pem:
            fd, cert_path = tempfile.mkstemp()
            try:
                os.write(fd, cert_pem.encode('utf-8'))
            finally:
                os.close(fd)
            paths.append(cert_path)

        # A key is only ever presented with its certificate, so never write
        # one that could not be used. fetch_pas_object rejects that input.
        if key_pem and cert_pem:
            fd, key_path = tempfile.mkstemp()
            try:
                os.write(fd, key_pem.encode('utf-8'))
            finally:
                os.close(fd)
            paths.append(key_path)

        if cert_path and key_path:
            yield (cert_path, key_path)
        elif cert_path:
            yield cert_path
        else:
            yield None
    finally:
        for path in paths:
            try:
                os.unlink(path)
            except OSError:
                pass


def resolve_object_property(object_property):
    """Map a caller-supplied property name to the key used in the CCP response."""
    if not object_property or object_property.lower() == 'password':
        return 'Content'
    elif object_property.lower() == 'username':
        return 'UserName'
    elif object_property.lower() == 'address':
        return 'Address'
    return object_property.capitalize()


def fetch_pas_object(
    url,
    app_id,
    object_query,
    webservice_id='',
    client_cert=None,
    client_key=None,
    verify=True,
    object_query_format='Exact',
    object_property='',
    reason=None,
    timeout=30,
):
    """Fetch an object from CyberArk CCP and return the requested property value.

    Raises CyberarkCCPError on any failure: missing "requests" library, transport
    error, non-2xx response, unparsable JSON, or a missing property.
    """
    if client_key and not client_cert:
        # TLS client authentication presents a certificate; the key only proves
        # ownership of it. A key alone would silently send the request with no
        # client certificate at all. A key bundled in client_cert's PEM needs no
        # client_key, so that case is unaffected.
        raise CyberarkCCPError(
            'client_key was given without client_cert. Provide the client certificate too, '
            'or pass a PEM that holds both the certificate and its key as client_cert.'
        )

    if not HAS_REQUESTS:
        raise CyberarkCCPError('The Python "requests" library is required for this operation.')

    webservice_id = webservice_id or 'AIMWebService'

    query_params = {
        'AppId': app_id,
        'Query': object_query,
        'QueryFormat': object_query_format,
    }
    if reason:
        query_params['reason'] = reason

    request_qs = '?' + urlencode(query_params, quote_via=quote)
    request_url = urljoin(url, '/'.join([webservice_id, 'api', 'Accounts']))

    try:
        with cert_files(client_cert, client_key) as cert:
            response = requests.get(
                request_url + request_qs,
                timeout=timeout,
                cert=cert,
                verify=verify,
                allow_redirects=False,
            )
    except requests.exceptions.RequestException as exc:
        raise CyberarkCCPError(f'Request to CyberArk CCP failed: {str(exc)}') from exc

    if not response.ok:
        raise CyberarkCCPError(f'CyberArk CCP returned HTTP {response.status_code}: {response.text}')

    try:
        data = response.json()
    except ValueError as exc:
        raise CyberarkCCPError(f'Failed to parse CyberArk CCP response as JSON: {str(exc)}') from exc

    prop = resolve_object_property(object_property)

    if prop not in data:
        raise CyberarkCCPError(f'Property {object_property!r} not found in CyberArk object. Available properties: Username, Password, Address.')

    return data[prop]
