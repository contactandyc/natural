# SPDX-FileCopyrightText: 2026 Andy Curtis <contactandyc@gmail.com>
# SPDX-License-Identifier: Apache-2.0
# Maintainer: Andy Curtis <contactandyc@gmail.com>

import re
from natural.normalizer.workspace import Workspace


class NaturalPreprocessor:
    def __init__(self, workspace: Workspace):
        self.workspace = workspace
        self.include_pattern = re.compile(
            r"^\s*INCLUDE\s+([A-Za-z0-9\-_]+)(.*)",
            re.IGNORECASE | re.MULTILINE,
            )

    def strip_comments(self, text: str) -> str:
        # Strip block / inline comments: /* ... */
        cleaned = re.sub(r"/\*.*?(?:\*/|$)", "", text)
        lines = []
        for line in cleaned.splitlines():
            stripped = line.strip()
            if stripped.startswith("*") and not stripped.startswith(("**", "*ISN", "*DATX", "*TIME")):
                continue
            lines.append(line)
        return "\n".join(lines)

    def join_continuations(self, text: str) -> str:
        """Joins lines when a WRITE/PRINT statement ends with a / continuation marker."""
        lines = text.splitlines()
        joined = []
        i = 0
        while i < len(lines):
            line = lines[i]
            # If line ends with '/' (Natural WRITE/PRINT line break) and next line is indented output
            while (
                    line.rstrip().endswith("/")
                    and i + 1 < len(lines)
                    and lines[i + 1].strip()
                    and not lines[i + 1].strip().upper().startswith(
                ("END-", "IF ", "READ ", "FIND ", "UPDATE", "GET ", "ESCAPE", "RESET", "PERFORM")
            )
            ):
                i += 1
                next_line = lines[i].strip()
                line = f"{line.rstrip()} {next_line}"
            joined.append(line)
            i += 1
        return "\n".join(joined)

    def expand(self, source_text: str, current_module: str, depth: int = 0) -> str:
        if depth > 20:
            raise RecursionError(f"Include depth exceeded in {current_module}")

        clean_source = self.strip_comments(source_text)
        clean_source = self.join_continuations(clean_source)

        def replace_include(match):
            module_name = match.group(1).upper()
            content = self.workspace._read_file(module_name, [".nsn", ".nsp", ".nss", ".txt", ".nsa"])
            if not content:
                return f"\n/* INCLUDE {module_name} NOT FOUND */\n"

            expanded = self.expand(content, module_name, depth + 1)
            return f"\n{expanded}\n"

        return self.include_pattern.sub(replace_include, clean_source)
