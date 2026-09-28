# tests/conftest.py
# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0

def pytest_addoption(parser):
    parser.addoption(
        "--bless",
        action="store_true",
        default=False,
        help="Update fixture === PYTHON === sections with compiler output",
    )
    parser.addoption(
        "--verbose-test",
        action="store_true",
        default=False,
        help="Print detailed IR passes, emitted Python code, and execution steps to the console",
    )
