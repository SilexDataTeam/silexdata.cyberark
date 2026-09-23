<!--
Copyright (c) Silex Data Solutions
SPDX-FileCopyrightText: Silex Data Solutions
SPDX-License-Identifier: Apache-2.0
-->

# Silex Data CyberArk Collection

[![Lint](https://github.com/SilexDataTeam/silexdata.cyberark/actions/workflows/lint.yml/badge.svg?branch=main)](https://github.com/SilexDataTeam/silexdata.cyberark/actions/workflows/lint.yml)
[![Nox (sanity + units)](https://github.com/SilexDataTeam/silexdata.cyberark/actions/workflows/nox.yml/badge.svg?branch=main)](https://github.com/SilexDataTeam/silexdata.cyberark/actions/workflows/nox.yml)
[![Coverage (integration)](https://github.com/SilexDataTeam/silexdata.cyberark/actions/workflows/coverage.yml/badge.svg?branch=main)](https://github.com/SilexDataTeam/silexdata.cyberark/actions/workflows/coverage.yml)

Ansible collection providing modules and plugins for retrieving credentials from CyberArk's Central Credential Provider (CCP).

This repository contains the `silexdata.cyberark` Ansible Collection.

## Code of Conduct

We follow [Ansible Code of Conduct](https://docs.ansible.com/ansible/latest/community/code_of_conduct.html) in all our interactions within this project.

If you encounter abusive behavior violating the [Ansible Code of Conduct](https://docs.ansible.com/ansible/latest/community/code_of_conduct.html), please refer to the [policy violations](https://docs.ansible.com/ansible/latest/community/code_of_conduct.html#policy-violations) section of the Code of Conduct for information on how to raise a complaint.

## External requirements

Some modules and plugins require external libraries. Please check the requirements for each plugin or module you use in the documentation to find out which requirements are needed. The `get_pas_object` module and lookup plugin both require the Python `requests` library. Both run on the controller, whichever host a task targets, so `requests` and network access to CCP are needed there, not on managed nodes.

## Included content

Please check the included content on the [Ansible Galaxy page for this collection](https://galaxy.ansible.com/ui/repo/published/silexdata/cyberark/).

## Using this collection

You must install this collection from [Ansible Galaxy](https://galaxy.ansible.com/ui/repo/published/silexdata/cyberark/) using the `ansible-galaxy` command-line tool, regardless of your Ansible installation type:

```shell
ansible-galaxy collection install silexdata.cyberark
```

You can also include it in a `requirements.yml` file and install it via `ansible-galaxy collection install -r requirements.yml` using the format:

```yaml
collections:
- name: silexdata.cyberark
```

Note that if you install the collection manually, it will not be upgraded automatically. To upgrade the collection to the latest available version, run the following command:

```bash
ansible-galaxy collection install silexdata.cyberark --upgrade
```

You can also install a specific version of the collection, for example, if you need to downgrade when something is broken in the latest version (please report an issue in this repository). Use the following syntax where `X.Y.Z` can be any [available version](https://galaxy.ansible.com/ui/repo/published/silexdata/cyberark/):

```bash
ansible-galaxy collection install silexdata.cyberark:==X.Y.Z
```

See [Ansible Using collections](https://docs.ansible.com/ansible/latest/user_guide/collections_using.html) for more details.

### Retrieving a credential with the `get_pas_object` module

```yaml
- name: Retrieve a password from CyberArk CCP
  silexdata.cyberark.get_pas_object:
    url: https://cyberark.example.com
    app_id: MyApp
    object_query: "Safe=MySafe;Object=MyAccount"
  register: result
  no_log: true
```

### Retrieving a credential with the `get_pas_object` lookup plugin

```yaml
- name: Retrieve a password from CyberArk CCP
  ansible.builtin.debug:
    msg: >-
      {{ lookup('silexdata.cyberark.get_pas_object', 'Safe=MySafe;Object=MyAccount',
         url='https://cyberark.example.com', app_id='MyApp') }}
```

## Contributing to this collection

All types of contributions are very welcome.

Every change goes through a pull request: branch from an up-to-date `main`,
commit with [Conventional Commits](https://www.conventionalcommits.org/)
messages, add or extend a changelog fragment under `changelogs/fragments/`,
and open a PR. It merges once every required check has passed; nobody pushes
to `main` directly. Merging never publishes anything below 1.0.0 - the first
release is cut deliberately by a `major_changes` fragment. The full procedure
is in `.claude/rules/workflow.md`.

You can find more information in the [developer guide for collections](https://docs.ansible.com/ansible/devel/dev_guide/developing_collections.html#contributing-to-collections), and in the [Ansible Community Guide](https://docs.ansible.com/ansible/latest/community/index.html).

### Running tests

See [here](https://docs.ansible.com/ansible/devel/dev_guide/developing_collections.html#testing-collections).

## Collection maintenance

To learn how to maintain / become a maintainer of this collection, refer to:

- [Maintainer guidelines](https://github.com/ansible/community-docs/blob/main/maintaining.rst).

It is necessary for maintainers of this collection to be subscribed to:

- The collection itself (the `Watch` button → `All Activity` in the upper right corner of the repository's homepage).

## Publishing New Version

See the [Releasing guidelines](https://github.com/ansible/community-docs/blob/main/releasing_collections.rst) to learn how to release this collection.

## Release notes

See the [changelog](https://github.com/SilexDataTeam/silexdata.cyberark/blob/main/CHANGELOG.md).

## More information

- [Ansible Collection overview](https://github.com/ansible-collections/overview)
- [Ansible User guide](https://docs.ansible.com/ansible/latest/user_guide/index.html)
- [Ansible Developer guide](https://docs.ansible.com/ansible/latest/dev_guide/index.html)
- [Ansible Community code of conduct](https://docs.ansible.com/ansible/latest/community/code_of_conduct.html)

## Licensing

This collection is licensed under the **Apache License, Version 2.0** by
default - see [COPYING](COPYING) - with two exceptions, each declared in the
file's own SPDX header. The full license texts are under [LICENSES/](LICENSES).

| Path | License |
| --- | --- |
| plugin code in `plugins/` (modules, lookups, filters, doc_fragments, ...) | `GPL-3.0-or-later` |
| `plugins/module_utils/` | `BSD-2-Clause` |
| everything else | `Apache-2.0` |

Plugin code is GPL-3.0-or-later because Ansible requires it for plugins that
run inside the controller, and ansible-test requires it for modules.
`module_utils` is BSD-2-Clause because it is copied into the payload that runs
on managed nodes, where a copyleft license would extend to every third-party
module importing it.

### Third-party code

`plugins/module_utils/cyberark_ccp.py` is derived from the CyberArk AIM / CCP
credential plugin of the [AWX Project](https://github.com/ansible/awx-plugins),
and keeps AWX's Apache License, Version 2.0, and its attribution. It is
therefore Apache-2.0 rather than this collection's usual BSD-2-Clause for
`module_utils`.

Contributions are accepted under these same terms. Before changing any license
header, read `.claude/rules/licensing.md` - in particular, code adapted from
another project keeps its original license and attribution.

Run `nox -e license-check` to verify compliance.
