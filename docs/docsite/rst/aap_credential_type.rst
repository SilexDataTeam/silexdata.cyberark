..
  SPDX-FileCopyrightText: Silex Data Solutions
  SPDX-License-Identifier: Apache-2.0

.. _ansible_collections.silexdata.cyberark.docsite.aap_credential_type:

A CyberArk CCP credential type for AAP and AWX
==============================================

The :ansplugin:`silexdata.cyberark.get_pas_object#module` module and the
:ansplugin:`silexdata.cyberark.get_pas_object#lookup` lookup plugin read their
connection settings from Ansible variables or environment variables if a task
does not set them. Store those settings in an Ansible Automation Platform (AAP)
or AWX credential and attach it to a job template. Playbooks can then retrieve
secrets without passing ``url``, ``app_id`` or a client certificate to every
task.

AAP and AWX have no built-in credential type that does this. The built-in
*CyberArk Central Credential Provider Lookup* type has a different job: it fills
in fields of other credentials from CCP, and it does not pass its own settings
to the playbook. This guide creates a custom credential type that does.

.. contents::
  :local:
  :depth: 1

What the credential provides
----------------------------

Each input of the credential type becomes the setting below. The guide sets
both the environment variable and the extra variable. Keep both, or remove
either injector section; see `Environment variables, extra variables, or both`_.

.. list-table::
  :header-rows: 1
  :widths: 22 33 33

  * - Credential input
    - Environment variable
    - Extra variable
  * - CCP URL
    - ``CYBERARK_CCP_URL``
    - ``cyberark_ccp_url``
  * - Application ID
    - ``CYBERARK_CCP_APP_ID``
    - ``cyberark_ccp_app_id``
  * - Web Service ID
    - ``CYBERARK_CCP_WEBSERVICE_ID``
    - ``cyberark_ccp_webservice_id``
  * - Disable TLS Certificate Verification
    - ``CYBERARK_CCP_VERIFY``, set to ``false`` only when ticked
    - ``cyberark_ccp_verify``, the same
  * - Client Certificate
    - ``CYBERARK_CCP_CLIENT_CERT_FILE``, the path of a file holding it
    - ``cyberark_ccp_client_cert_file``, the same
  * - Client Private Key
    - ``CYBERARK_CCP_CLIENT_KEY_FILE``, the path of a file holding it
    - ``cyberark_ccp_client_key_file``, the same

The certificate and key are written to files, like the private key of an SSH
Machine credential. The ``*_FILE`` settings carry the path of each file, not
the PEM text. AAP and AWX create the files in the job's private data directory
and delete them when the job ends.

Each name here maps to the plugins' option of the same name without its
prefix. ``cyberark_ccp_client_cert_file`` sets ``client_cert_file``, for
example. The plugins also accept ``CYBERARK_CCP_CLIENT_CERT`` and
``CYBERARK_CCP_CLIENT_KEY``, along with their variable forms, holding the PEM
text itself. This credential type does not set those.

Input configuration
-------------------

.. code-block:: yaml

  ---
  fields:
    - id: url
      label: CCP URL
      type: string
      format: url
      help_text: Base URL of the CyberArk CCP endpoint, for example https://cyberark.example.com.
    - id: app_id
      label: Application ID
      type: string
      secret: true
      help_text: The Application ID registered in CyberArk for this caller.
    - id: webservice_id
      label: Web Service ID
      type: string
      help_text: The CCP Web Service ID. Leave blank to use AIMWebService.
    - id: client_cert
      label: Client Certificate
      type: string
      multiline: true
      secret: true
      help_text: >-
        PEM-encoded client certificate for mutual TLS. It may also hold the matching
        private key. Leave blank if CCP does not authenticate this application by certificate.
    - id: client_key
      label: Client Private Key
      type: string
      format: ssh_private_key
      multiline: true
      secret: true
      help_text: >-
        PEM-encoded private key matching the client certificate. It must not be encrypted.
        Leave blank if the client certificate holds its key.
    - id: skip_verify
      label: Disable TLS Certificate Verification
      type: boolean
      help_text: Do not verify the CCP server's TLS certificate. Only for testing.
  required:
    - url
    - app_id

Notes on these fields:

* **Client Private Key** uses ``format: ssh_private_key``, as the SSH Machine
  credential does. AAP validates that it is a PEM private key and adds a final
  newline if it is missing. Any PEM private key passes, not only SSH keys,
  including PKCS #8 (``BEGIN PRIVATE KEY``) keys.
* **Client Certificate** has no ``format``. AAP has no format for certificates,
  and ``ssh_private_key`` would reject a certificate that does not include its
  key. It is ``secret`` because it may include the key.
* **TLS verification is an opt-out.** AAP injects ``False`` for a boolean input
  that a credential does not store, whatever the field's ``default``. That
  happens, for example, when a credential is created through the API without
  it. A *Verify* input would therefore turn verification off for such
  credentials. *Disable TLS Certificate Verification* fails safe instead.

Injector configuration
----------------------

.. code-block:: yaml+jinja

  ---
  file:
    template.client_cert: '{{ client_cert }}'
    template.client_key: '{{ client_key }}'
  env:
    CYBERARK_CCP_URL: '{{ url }}'
    CYBERARK_CCP_APP_ID: '{{ app_id }}'
    CYBERARK_CCP_WEBSERVICE_ID: '{{ webservice_id }}'
    CYBERARK_CCP_VERIFY: '{% if skip_verify %}false{% endif %}'
    CYBERARK_CCP_CLIENT_CERT_FILE: '{% if client_cert %}{{ tower.filename.client_cert }}{% endif %}'
    CYBERARK_CCP_CLIENT_KEY_FILE: '{% if client_key %}{{ tower.filename.client_key }}{% endif %}'
  extra_vars:
    cyberark_ccp_url: '{{ url }}'
    cyberark_ccp_app_id: '{{ app_id }}'
    cyberark_ccp_webservice_id: '{{ webservice_id }}'
    cyberark_ccp_verify: '{% if skip_verify %}false{% endif %}'
    cyberark_ccp_client_cert_file: '{% if client_cert %}{{ tower.filename.client_cert }}{% endif %}'
    cyberark_ccp_client_key_file: '{% if client_key %}{{ tower.filename.client_key }}{% endif %}'

Why the ``{% if %}`` conditions are needed:

* **AAP writes every file template, even an empty one.** Without the
  condition, a credential without a certificate or key would still point
  ``CYBERARK_CCP_CLIENT_CERT_FILE`` or ``CYBERARK_CCP_CLIENT_KEY_FILE`` at an
  empty file. The plugins reject an empty file rather than silently sending no
  certificate.
* **AAP renders an input left blank as an empty string.** The plugins treat an
  empty value as unset. A blank Web Service ID therefore falls back to
  ``AIMWebService``, and ``CYBERARK_CCP_VERIFY`` stays empty, so verification
  stays on, unless *Disable TLS Certificate Verification* is ticked.

Environment variables, extra variables, or both
-----------------------------------------------

The plugins use a setting from the first of these sources that sets it:

1. the option set on the task or the lookup call,
2. the ``cyberark_ccp_*`` Ansible variable,
3. the ``CYBERARK_CCP_*`` environment variable.

This is the order Ansible applies to plugin options. An option set on a task
still overrides the credential, so one play can point a single task somewhere
else.

* **Environment variables only:** delete the ``extra_vars`` section. The
  settings never become play variables, so a task such as
  ``ansible.builtin.debug: var=vars`` cannot print them. This is the choice to
  make unless you need the next one.
* **Extra variables only:** delete the ``env`` section. Choose this when
  playbooks need the values themselves, for example
  ``"{{ cyberark_ccp_url }}"`` in a message or another module's option. Extra
  variables have the highest precedence in Ansible, so they also override any
  ``cyberark_ccp_*`` variables set in the inventory.
* **Both:** keep both sections, as above. The extra variables win, and they
  hold the same values.

The client certificate and key are resolved together. They come from the first
source that sets any one of ``client_cert``, ``client_cert_file``,
``client_key`` or ``client_key_file``. A key from the credential is therefore
never paired with a certificate that a task sets itself.

Creating the credential type
----------------------------

In the web interface
~~~~~~~~~~~~~~~~~~~~

1. Open **Credential Types**. It is under **Automation Execution >
   Infrastructure** in AAP 2.5 and later, and under **Administration** in AWX
   and earlier AAP releases.
2. Create a credential type named, for example, ``CyberArk CCP Connection``.
3. Paste the `Input configuration`_ into **Input configuration** and the
   `Injector configuration`_ into **Injector configuration**, both as YAML.
4. Save it, then create a credential of this type with your CCP URL,
   Application ID, and certificate and key if CCP needs them.
5. Add the credential to each job template whose playbooks retrieve secrets
   from CCP.

As code
~~~~~~~

With the ``infra.aap_configuration`` collection, the
``controller_credential_types`` role creates it from a variable like the one
below. Mark each injector value ``!unsafe``: otherwise Ansible renders the
templates itself before AAP receives them.

.. code-block:: yaml+jinja

  ---
  controller_credential_types:
    - name: CyberArk CCP Connection
      description: Connection settings for the silexdata.cyberark collection.
      kind: cloud
      inputs:
        fields:
          - id: url
            label: CCP URL
            type: string
            format: url
            help_text: Base URL of the CyberArk CCP endpoint, for example https://cyberark.example.com.
          - id: app_id
            label: Application ID
            type: string
            secret: true
            help_text: The Application ID registered in CyberArk for this caller.
          - id: webservice_id
            label: Web Service ID
            type: string
            help_text: The CCP Web Service ID. Leave blank to use AIMWebService.
          - id: client_cert
            label: Client Certificate
            type: string
            multiline: true
            secret: true
            help_text: >-
              PEM-encoded client certificate for mutual TLS. It may also hold the matching
              private key. Leave blank if CCP does not authenticate this application by certificate.
          - id: client_key
            label: Client Private Key
            type: string
            format: ssh_private_key
            multiline: true
            secret: true
            help_text: >-
              PEM-encoded private key matching the client certificate. It must not be encrypted.
              Leave blank if the client certificate holds its key.
          - id: skip_verify
            label: Disable TLS Certificate Verification
            type: boolean
            help_text: Do not verify the CCP server's TLS certificate. Only for testing.
        required:
          - url
          - app_id
      injectors:
        file:
          template.client_cert: !unsafe '{{ client_cert }}'
          template.client_key: !unsafe '{{ client_key }}'
        env:
          CYBERARK_CCP_URL: !unsafe '{{ url }}'
          CYBERARK_CCP_APP_ID: !unsafe '{{ app_id }}'
          CYBERARK_CCP_WEBSERVICE_ID: !unsafe '{{ webservice_id }}'
          CYBERARK_CCP_VERIFY: !unsafe '{% if skip_verify %}false{% endif %}'
          CYBERARK_CCP_CLIENT_CERT_FILE: !unsafe '{% if client_cert %}{{ tower.filename.client_cert }}{% endif %}'
          CYBERARK_CCP_CLIENT_KEY_FILE: !unsafe '{% if client_key %}{{ tower.filename.client_key }}{% endif %}'
        extra_vars:
          cyberark_ccp_url: !unsafe '{{ url }}'
          cyberark_ccp_app_id: !unsafe '{{ app_id }}'
          cyberark_ccp_webservice_id: !unsafe '{{ webservice_id }}'
          cyberark_ccp_verify: !unsafe '{% if skip_verify %}false{% endif %}'
          cyberark_ccp_client_cert_file: !unsafe '{% if client_cert %}{{ tower.filename.client_cert }}{% endif %}'
          cyberark_ccp_client_key_file: !unsafe '{% if client_key %}{{ tower.filename.client_key }}{% endif %}'

Red Hat's `custom credential types documentation
<https://docs.redhat.com/en/documentation/red_hat_ansible_automation_platform/2.5/html/using_automation_execution/assembly-controller-custom-credentials>`_
covers the input and injector schema in full.

Using it in a playbook
----------------------

With the credential attached to the job template, tasks need only the query:

.. code-block:: yaml+jinja

  ---
  - name: Retrieve the database password
    silexdata.cyberark.get_pas_object:
      object_query: Safe=Databases;Object=app-db
    register: app_db_password
    no_log: true

  - name: Retrieve the database username
    ansible.builtin.set_fact:
      app_db_user: "{{ lookup('silexdata.cyberark.get_pas_object', 'Safe=Databases;Object=app-db', object_property='Username') }}"

Both plugins run on the controller, which in AAP means inside the job's
execution environment. That is where the environment variables are set and the
certificate and key files are written, so the managed hosts need nothing.
