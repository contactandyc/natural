# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

from decimal import Decimal
from typing import Any


def unmask_decimal(val: Any) -> Decimal:
    """Parses alphanumeric strings containing currency, commas, trailing signs, CR/DB, or parens into Decimals."""
    if val is None or val == "":
        return Decimal("0")
    s = str(val).strip().replace("$", "").replace(",", "").replace(" ", "").replace("+", "")
    if not s:
        return Decimal("0")

    is_neg = (
            s.endswith("-")
            or s.startswith("-")
            or s.endswith(("CR", "DB", "cr", "db"))
            or (s.startswith("(") and s.endswith(")"))
    )
    clean_digits = s.rstrip("-CRDBcrdb").lstrip("-+(").rstrip(")").strip()
    if not clean_digits:
        return Decimal("0")
    num = Decimal(clean_digits)
    return -num if is_neg else num


def unmask_integer(val: Any) -> int:
    """Parses alphanumeric strings into signed integers."""
    if val is None or val == "":
        return 0
    return int(unmask_decimal(val))
