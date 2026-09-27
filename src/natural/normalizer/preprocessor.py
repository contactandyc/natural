# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

import re
from natural.normalizer.workspace import Workspace

class NaturalPreprocessor:
    def __init__(self, workspace: Workspace):
        self.workspace = workspace
        self.include_pattern = re.compile(
            r"^\s*INCLUDE\s+([A-Z0-9\-\_]+)(.*)",
            re.IGNORECASE | re.MULTILINE
        )
        # Matches /* ... */ or /* ... up to end-of-line
        self.comment_pattern = re.compile(r"/\*.*?(?:\*/|$)", re.DOTALL)

    def strip_comments(self, text: str) -> str:
        # Strip block / inline comments: /* ... */
        cleaned = re.sub(r"/\*.*?(?:\*/|$)", "", text)
        # Strip full-line comments starting with *
        lines = []
        for line in cleaned.splitlines():
            if line.strip().startswith("*") and not line.strip().startswith(("**", "*ISN", "*DATX", "*TIME")):
                continue
            lines.append(line)
        return "\n".join(lines)

    def expand(self, source_text: str, current_module: str, depth: int = 0) -> str:
        if depth > 20:
            raise RecursionError(f"Include depth exceeded in {current_module}")

        # Strip comments first so INCLUDES or pseudo-statements in comments are ignored
        clean_source = self.strip_comments(source_text)

        def replace_include(match):
            module_name = match.group(1).upper()
            content = self.workspace._read_file(module_name, ['.nsn', '.nsp', '.nss', '.txt', '.nsa'])
            if not content:
                return f"\n/* INCLUDE {module_name} NOT FOUND */\n"

            expanded = self.expand(content, module_name, depth + 1)
            return f"\n{expanded}\n"

        return self.include_pattern.sub(replace_include, clean_source)
