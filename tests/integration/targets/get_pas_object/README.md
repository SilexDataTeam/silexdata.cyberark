<!--
SPDX-FileCopyrightText: Silex Data Solutions
SPDX-License-Identifier: Apache-2.0
-->

# get_pas_object integration target

This target validates the `silexdata.cyberark.get_pas_object` module and lookup
plugin. Tests are grouped by category under `tasks/tests/`; `tasks/main.yml`
simply discovers and runs every file there.

## Test categories

- `expected-failures.yml` — argument-spec validation (required `url`, `app_id`,
  `object_query` params). Service-independent; always runs.
- `check-mode.yml` — asserts the module runs in check mode and makes no changes.
  Service-independent; fails if the module does not support check mode.
- `expected-return-values.yml` — **live**, service-dependent checks that
  exercise both the module and the lookup plugin against a configured CCP
  endpoint. Skipped when the service is unavailable. Assertions are structural
  (the call round-trips a request rather than crashing locally) since CI does
  not have access to a real CyberArk CCP tenant with a known object to query.

## Service availability

The `setup_cyberark` role (a dependency declared in `meta/main.yml`) probes the
CyberArk CCP endpoint and sets `setup_cyberark_service_available`. Live test
blocks are gated on this flag (remapped to `get_pas_object_service_available`
in `defaults/main.yml`).

- **Service down (default):** live tests are skipped and a warning is emitted.
- **Service down with `setup_cyberark_require_service: true`:** the run fails.

Only tests that genuinely require the service are skipped when it is down; all
other tests still run and are expected to fail on real problems.

## Running locally

From within the collection path (`.../ansible_collections/silexdata/cyberark`):

```bash
ansible-test integration get_pas_object --docker -v --requirements
```

To run the live tests, copy `tests/integration/integration_config.yml.template`
to `tests/integration/integration_config.yml` and supply real credentials.
