# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>


def convert_edit_mask(mask: str) -> str:
    """Converts Natural date edit mask to strftime/strptime format."""
    return mask.replace("YYYY", "%Y").replace("YY", "%y").replace("MM", "%m").replace("DD", "%d")


def format_numeric_edit_mask(target: str, src_ref: str, mask: str) -> str:
    """Emits formatted Python f-string interpolation for Natural numeric edit masks."""
    raw_mask = mask.strip().upper()

    has_currency = "$" in raw_mask
    prefix = "$" if has_currency else ""
    cleaned = raw_mask.replace("$", "").strip()

    suffix_token = None
    if cleaned.endswith("CR"):
        suffix_token = "CR"
        cleaned = cleaned[:-2].strip()
    elif cleaned.endswith("DB"):
        suffix_token = "DB"
        cleaned = cleaned[:-2].strip()
    elif cleaned.endswith("-"):
        suffix_token = "-"
        cleaned = cleaned[:-1].strip()
    elif cleaned.endswith("+"):
        suffix_token = "+"
        cleaned = cleaned[:-1].strip()

    prefix_sign = None
    if not suffix_token:
        if cleaned.startswith("+"):
            prefix_sign = "+"
            cleaned = cleaned[1:].strip()
        elif cleaned.startswith("-"):
            prefix_sign = "-"
            cleaned = cleaned[1:].strip()

    decimals = 0
    if "." in cleaned:
        int_part, dec_part = cleaned.split(".", 1)
        decimals = len(dec_part)
    else:
        int_part = cleaned

    use_comma = "," in int_part
    has_zero_suppression = int_part.count("Z") > 0
    total_num_width = len(int_part) + (1 + decimals if decimals > 0 else 0)

    is_fixed_column = has_currency or suffix_token in ("CR", "DB")
    if is_fixed_column and has_zero_suppression:
        fmt_spec = f">{total_num_width},.{decimals}f" if use_comma else f">{total_num_width}.{decimals}f"
        pos_padding = "  " if suffix_token in ("CR", "DB") else (" " if suffix_token in ("-", "+") else "")
    else:
        fmt_spec = f",.{decimals}f" if use_comma else f".{decimals}f"
        pos_padding = ""

    value_expr = f"abs({src_ref})" if (suffix_token or prefix_sign) else src_ref

    suffix_code = ""
    if suffix_token == "CR":
        suffix_code = f"{{'CR' if {src_ref} < 0 else '{pos_padding}'}}"
    elif suffix_token == "DB":
        suffix_code = f"{{'DB' if {src_ref} < 0 else '{pos_padding}'}}"
    elif suffix_token == "-":
        suffix_code = f"{{'-' if {src_ref} < 0 else '{pos_padding}'}}"
    elif suffix_token == "+":
        suffix_code = f"{{'-' if {src_ref} < 0 else '+'}}"

    prefix_code = prefix
    if prefix_sign == "+":
        prefix_code += f"{{'-' if {src_ref} < 0 else '+'}}"
    elif prefix_sign == "-":
        prefix_code += f"{{'-' if {src_ref} < 0 else ' '}}"

    return f'{target} = f"{prefix_code}{{{value_expr}:{fmt_spec}}}{suffix_code}"'
