# SPDX-FileCopyrightText: Silex Data Solutions
# SPDX-License-Identifier: Apache-2.0

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import os

import pytest


@pytest.fixture(autouse=True)
def no_ccp_environment(monkeypatch):
    """Clear every CYBERARK_CCP_* variable, which the plugins fall back to.

    CI may export them for the integration tests; a test that needs one sets it.
    """
    for name in list(os.environ):
        if name.startswith("CYBERARK_CCP_"):
            monkeypatch.delenv(name)
