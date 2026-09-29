# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

PYTHON_KEYWORDS = {
    "class", "def", "return", "pass", "if", "else", "elif",
    "import", "from", "for", "while", "break", "continue",
    "and", "or", "not", "is", "in", "lambda", "global",
    "nonlocal", "try", "except", "finally", "raise", "yield",
    "with", "as", "assert", "async", "await",
}


def clean_name(name: str) -> str:
    """Converts Natural/DDM identifiers into safe Pythonic snake_case names."""
    clean = name.split(".")[-1].replace("#", "").replace("-", "_").lower()
    if clean in PYTHON_KEYWORDS or clean == "class":
        return f"{clean}_"
    return clean


def clean_func_name(name: str) -> str:
    """Normalizes user-defined function names to prefixed 'fn_<name>'."""
    clean = name.replace("#", "_").replace("-", "_").lower()
    while clean.startswith(("fn_", "f_", "udf_")):
        if clean.startswith("fn_"):
            clean = clean[3:]
        elif clean.startswith("f_"):
            clean = clean[2:]
        elif clean.startswith("udf_"):
            clean = clean[4:]
    return f"fn_{clean}"


def to_pascal_case(name: str) -> str:
    """Converts module or variable names into PascalCase for Python class names."""
    clean = name.split(".")[-1].replace("#", "").replace("-", "_").lower()
    return "".join(part.title() for part in clean.split("_") if part)
