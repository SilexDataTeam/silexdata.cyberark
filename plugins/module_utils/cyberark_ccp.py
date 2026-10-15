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
        client_cert_file=dict(type='path', no_log=False),
        client_key=dict(type='str', no_log=True),
        client_key_file=dict(type='path', no_log=False),
        verify=dict(type='bool', default=True),
        object_query_format=dict(type='str', default='Exact', choices=['Exact', 'Regexp']),
        object_property=dict(type='str', default=''),
        reason=dict(type='str', no_log=True),
    )


# Connection options a caller may leave unset, to be read instead from an
# Ansible variable and then from an environment variable on the controller -
# the precedence Ansible gives a plugin's own options. fallback_names() derives
# the two names. Documented by the cyberark_ccp doc fragment.
FALLBACK_OPTIONS = (
    'url',
    'app_id',
    'webservice_id',
    'verify',
    'client_cert',
    'client_cert_file',
    'client_key',
    'client_key_file',
)

# The client certificate and its key, each given as PEM content or as a path.
# They are resolved together, from a single source, so a key is never paired
# with a certificate that came from somewhere else.
CLIENT_AUTH_OPTIONS = ('client_cert', 'client_cert_file', 'client_key', 'client_key_file')


class CyberarkCCPError(Exception):
    """Raised when a CyberArk CCP request fails or its response is unusable."""


def fallback_names(option):
    """Return the (Ansible variable, environment variable) names an option falls back to."""
    return 'cyberark_ccp_' + option, 'CYBERARK_CCP_' + option.upper()


def _is_set(value):
    # An empty string counts as unset at every level: AAP renders an injector
    # whose credential input was left blank as one.
    return value is not None and value != ''


def _client_auth_error(given, name_of):
    """Return why the given client certificate/key options cannot be used together, or None.

    ``given`` holds the CLIENT_AUTH_OPTIONS that are set, and ``name_of`` maps
    each option to the name the caller set it by, for the message.
    """
    for content, path in (('client_cert', 'client_cert_file'), ('client_key', 'client_key_file')):
        if content in given and path in given:
            return f'{name_of(content)} and {name_of(path)} are mutually exclusive; set only one of them.'

    if given and 'client_cert' not in given and 'client_cert_file' not in given:
        # TLS client authentication presents a certificate; the key only proves
        # ownership of it. A key alone would silently send the request with no
        # client certificate at all. A key bundled in client_cert's PEM needs no
        # client_key, so that case is unaffected.
        key = 'client_key' if 'client_key' in given else 'client_key_file'
        return (
            f'{name_of(key)} was given without {name_of("client_cert")} or {name_of("client_cert_file")}. '
            f'Provide the client certificate too, or pass a PEM that holds both the certificate and its key '
            f'as {name_of("client_cert")}.'
        )

    return None


def resolve_fallbacks(direct, variables, environ, template):
    """Resolve the FALLBACK_OPTIONS from the caller's own options, then Ansible variables, then the environment.

    ``template`` renders a variable's value, since plugins receive variables
    unrendered. Each option is taken from the first source that sets it, except
    the CLIENT_AUTH_OPTIONS, which all come from the first source that sets any
    of them. Options set nowhere are left out, so the caller's defaults apply.

    Raises CyberarkCCPError when that source's certificate and key options
    cannot be used together.
    """
    sources = (
        (direct, lambda option: option, lambda value: value),
        (variables or {}, lambda option: fallback_names(option)[0], template),
        (environ, lambda option: fallback_names(option)[1], lambda value: value),
    )

    def read(source, option):
        container, name_of, render = source
        value = container.get(name_of(option))
        return render(value) if _is_set(value) else None

    resolved = {}
    for option in FALLBACK_OPTIONS:
        if option in CLIENT_AUTH_OPTIONS:
            continue
        for source in sources:
            value = read(source, option)
            if _is_set(value):
                resolved[option] = value
                break

    for source in sources:
        found = {option: read(source, option) for option in CLIENT_AUTH_OPTIONS}
        found = {option: value for option, value in found.items() if _is_set(value)}
        if found:
            error = _client_auth_error(found, source[1])
            if error:
                raise CyberarkCCPError(error)
            resolved.update(found)
            break

    return resolved


@contextlib.contextmanager
def cert_files(cert_pem, key_pem, cert_file=None, key_file=None):
    """Yield the requests-compatible cert argument for a client certificate and key.

    Each is given as PEM content, which is written to a temp file removed
    afterwards, or as the path of an existing file, which is used as it is.
    """
    paths = []
    try:
        cert_path, key_path = cert_file, key_file

        if cert_pem:
            fd, cert_path = tempfile.mkstemp()
            try:
                os.write(fd, cert_pem.encode('utf-8'))
            finally:
                os.close(fd)
            paths.append(cert_path)

        # A key is only ever presented with its certificate, so never write
        # one that could not be used. fetch_pas_object rejects that input.
        if not cert_path:
            key_path = None
        elif key_pem:
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
    client_cert_file=None,
    client_key_file=None,
    verify=True,
    object_query_format='Exact',
    object_property='',
    reason=None,
    timeout=30,
):
    """Fetch an object from CyberArk CCP and return the requested property value.

    Raises CyberarkCCPError on any failure: an unusable client certificate or
    key, missing "requests" library, transport error, non-2xx response,
    unparsable JSON, or a missing property.
    """
    given = {
        option
        for option, value in (
            ('client_cert', client_cert),
            ('client_cert_file', client_cert_file),
            ('client_key', client_key),
            ('client_key_file', client_key_file),
        )
        if value
    }
    error = _client_auth_error(given, lambda option: option)
    if error:
        raise CyberarkCCPError(error)

    for option, path in (('client_cert_file', client_cert_file), ('client_key_file', client_key_file)):
        # Checked here because requests raises a bare OSError for a missing
        # file, and an empty one fails only later, inside the TLS handshake.
        if path and not os.path.isfile(path):
            raise CyberarkCCPError(f'{option} {path!r} does not exist or is not a file.')
        if path and not os.path.getsize(path):
            raise CyberarkCCPError(f'{option} {path!r} is empty.')

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
        with cert_files(client_cert, client_key, client_cert_file, client_key_file) as cert:
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
