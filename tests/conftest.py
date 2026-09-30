# tests/conftest.py

def pytest_addoption(parser):
    parser.addoption(
        "--bless",
        action="store_true",
        default=False,
        help="Update fixture === PYTHON === sections with compiler output",
    )
    parser.addoption(
        "--evaluate",
        action="store_true",
        default=False,
        help="Skip syntactic snapshot diff failures and assert behavioral execution only",
    )
    parser.addoption(
        "--verbose-test",
        action="store_true",
        default=False,
        help="Print detailed IR passes, emitted Python code, and execution steps to the console",
    )
