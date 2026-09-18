#!/usr/bin/env python3
"""Inject canonical external-directory permissions into an OpenCode JSONC file."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CANONICAL_EXTERNAL_DIRECTORIES = (
    "/Users/guilhermebomfim/developer/planning-docs/*/.planning/**/*",
    "~/developer/planning-docs/*/.planning/**/*",
    "/Users/guilhermebomfim/project-workspaces/**/*",
    "~/developer/planning-docs/*/*/prs/**/*",
    "/Users/guilhermebomfim/developer/planning-docs/*/*/prs/**/*",
)
MAX_PARSE_DEPTH = 256


class InjectionError(ValueError):
    """Raised when the OpenCode JSONC structure cannot be safely updated."""


@dataclass
class Node:
    kind: str
    start: int
    end: int
    value: Any = None
    children: dict[str, tuple[int, "Node"]] | None = None

    def __post_init__(self) -> None:
        if self.children is None:
            self.children = {}


def mask_comments(text: str) -> str:
    masked = list(text)
    index = 0
    in_string = False
    escaped = False
    while index < len(text):
        char = text[index]
        next_char = text[index + 1] if index + 1 < len(text) else ""
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            index += 1
        elif char == "/" and next_char == "/":
            masked[index] = " "
            masked[index + 1] = " "
            index += 2
            while index < len(text) and text[index] not in "\r\n":
                masked[index] = " "
                index += 1
        elif char == "/" and next_char == "*":
            masked[index] = " "
            masked[index + 1] = " "
            index += 2
            while index + 1 < len(text) and text[index:index + 2] != "*/":
                if text[index] not in "\r\n":
                    masked[index] = " "
                index += 1
            if index + 1 >= len(text):
                raise InjectionError("unterminated JSONC block comment")
            masked[index] = " "
            masked[index + 1] = " "
            index += 2
        else:
            index += 1
    return "".join(masked)


class JsoncParser:
    def __init__(self, source: str) -> None:
        self.source = source
        self.masked = mask_comments(source)
        self.decoder = json.JSONDecoder(parse_constant=self.reject_constant)

    @staticmethod
    def reject_constant(constant: str) -> None:
        raise InjectionError(f"invalid JSONC constant: {constant}")

    def skip_whitespace(self, index: int) -> int:
        while index < len(self.masked) and self.masked[index].isspace():
            index += 1
        return index

    def parse(self) -> Node:
        root = self.parse_value(0)
        if root.kind != "object":
            raise InjectionError("Rulesync OpenCode output must be a JSON object")
        trailing = self.skip_whitespace(root.end)
        if trailing != len(self.masked):
            raise InjectionError("trailing JSONC content after root object")
        return root

    def parse_value(self, index: int, depth: int = 0) -> Node:
        if depth > MAX_PARSE_DEPTH:
            raise InjectionError(f"JSONC nesting exceeds maximum depth of {MAX_PARSE_DEPTH}")
        index = self.skip_whitespace(index)
        if index >= len(self.masked):
            raise InjectionError("unexpected end of JSONC input")
        if self.masked[index] == "{":
            start = index
            index = self.skip_whitespace(index + 1)
            children: dict[str, tuple[int, Node]] = {}
            while True:
                if index >= len(self.masked):
                    raise InjectionError("unterminated JSONC object")
                if self.masked[index] == "}":
                    return Node("object", start, index + 1, children=children)
                key_start = index
                try:
                    key, key_end = self.decoder.raw_decode(self.masked, index)
                except json.JSONDecodeError as error:
                    raise InjectionError(f"invalid JSONC object key: {error.msg}") from error
                if not isinstance(key, str):
                    raise InjectionError("JSONC object key is not a string")
                if key in children:
                    raise InjectionError(f"duplicate JSONC object key: {key!r}")
                index = self.skip_whitespace(key_end)
                if index >= len(self.masked) or self.masked[index] != ":":
                    raise InjectionError("JSONC object key is missing a colon")
                value = self.parse_value(index + 1, depth + 1)
                children[key] = (key_start, value)
                index = self.skip_whitespace(value.end)
                if index < len(self.masked) and self.masked[index] == ",":
                    index = self.skip_whitespace(index + 1)
                elif index >= len(self.masked) or self.masked[index] != "}":
                    raise InjectionError("JSONC object member is missing a comma")
        if self.masked[index] == "[":
            start = index
            index = self.skip_whitespace(index + 1)
            values: list[Node] = []
            while True:
                if index >= len(self.masked):
                    raise InjectionError("unterminated JSONC array")
                if self.masked[index] == "]":
                    return Node("array", start, index + 1, value=values)
                value = self.parse_value(index, depth + 1)
                values.append(value)
                index = self.skip_whitespace(value.end)
                if index < len(self.masked) and self.masked[index] == ",":
                    index = self.skip_whitespace(index + 1)
                elif index >= len(self.masked) or self.masked[index] != "]":
                    raise InjectionError("JSONC array member is missing a comma")
        try:
            value, end = self.decoder.raw_decode(self.masked, index)
        except json.JSONDecodeError as error:
            raise InjectionError(f"invalid JSONC value: {error.msg}") from error
        return Node("value", index, end, value=value)


def member(node: Node, name: str) -> Node | None:
    if node.children is None:
        return None
    entry = node.children.get(name)
    return entry[1] if entry is not None else None


def validate_patterns(external_directories: list[str]) -> None:
    if len(external_directories) != len(set(external_directories)):
        raise InjectionError("duplicate external-directory pattern arguments are not allowed")
    if set(external_directories) != set(CANONICAL_EXTERNAL_DIRECTORIES):
        raise InjectionError("external-directory patterns must exactly match the canonical list")


def indent_at(source: str, position: int) -> str:
    line_start = source.rfind("\n", 0, position) + 1
    prefix = source[line_start:position]
    return prefix if not prefix.strip() else ""


def member_indent(source: str, node: Node) -> str:
    if node.children:
        first = next(iter(node.children.values()))
        return indent_at(source, first[0])
    return indent_at(source, node.end - 1) + "  "


def line_ending(source: str) -> str:
    return "\r\n" if "\r\n" in source else "\n"


def object_insert(source: str, masked: str, node: Node, rendered_members: list[str]) -> list[tuple[int, str]]:
    close = node.end - 1
    newline = line_ending(source)
    separator = ""
    if node.children:
        last = max(node.children.values(), key=lambda item: item[1].end)[1]
        if not masked[last.end:close].lstrip().startswith(","):
            if last.end == close:
                separator = ","
            else:
                return [(last.end, ","), (close, newline + ("," + newline).join(rendered_members) + newline + indent_at(source, close))]
    return [(close, separator + newline + ("," + newline).join(rendered_members) + newline + indent_at(source, close))]


def inject(path: Path, external_directories: list[str]) -> None:
    validate_patterns(external_directories)
    with path.open("r", encoding="utf-8", newline="") as handle:
        source = handle.read()
    parser = JsoncParser(source)
    masked = parser.masked
    root = parser.parse()

    if member(root, "$schema") is None:
        schema_indent = member_indent(source, root)
        schema = f'{schema_indent}"$schema": "https://opencode.ai/config.json"'
        edits = object_insert(source, masked, root, [schema])
        for position, replacement in sorted(edits, reverse=True):
            source = source[:position] + replacement + source[position:]
        parser = JsoncParser(source)
        masked = parser.masked
        root = parser.parse()

    permission = member(root, "permission")
    if permission is None:
        permission = Node("object", 0, 0, children={})
        permission_missing = True
    elif permission.kind != "object":
        raise InjectionError("existing OpenCode permission rule conflicts with canonical external-directory rules")
    else:
        permission_missing = False

    external = member(permission, "external_directory")
    if external is not None and external.kind != "object":
        raise InjectionError("existing OpenCode external_directory rule conflicts with canonical external-directory rules")

    canonical_patterns = set(external_directories)
    if external is not None:
        for pattern, (_, existing) in (external.children or {}).items():
            if existing.value == "allow" and pattern not in canonical_patterns:
                raise InjectionError(
                    f"existing OpenCode external_directory allow rule is outside the canonical list: {pattern!r}"
                )

    for pattern in external_directories:
        if external is not None:
            existing = member(external, pattern)
            if existing is not None and existing.value != "allow":
                raise InjectionError(f"existing OpenCode external_directory rule conflicts for {pattern!r}")

    edits: list[tuple[int, str]] = []
    if external is not None:
        missing = [pattern for pattern in external_directories if member(external, pattern) is None]
        if missing:
            child_indent = member_indent(source, external)
            edits.extend(object_insert(
                source,
                masked,
                external,
                [f'{child_indent}{json.dumps(pattern)}: "allow"' for pattern in missing],
            ))
    elif permission_missing:
        root_indent = member_indent(source, root)
        child_indent = root_indent + "  "
        newline = line_ending(source)
        external_value = "{" + newline + ("," + newline).join(
            f'{child_indent}{json.dumps(pattern)}: "allow"' for pattern in external_directories
        ) + newline + root_indent + "}"
        edits.extend(object_insert(source, masked, root, [f'{root_indent}"permission": {external_value}']))
    else:
        permission_indent = member_indent(source, permission)
        newline = line_ending(source)
        external_value = "{" + newline + ("," + newline).join(
            f'{permission_indent}{json.dumps(pattern)}: "allow"' for pattern in external_directories
        ) + newline + indent_at(source, permission.end - 1) + "  }"
        edits.extend(object_insert(
            source,
            masked,
            permission,
            [f'{permission_indent}"external_directory": {external_value}'],
        ))

    for position, replacement in sorted(edits, reverse=True):
        source = source[:position] + replacement + source[position:]
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(source)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inject allow rules for external directories into an OpenCode JSONC config."
    )
    parser.add_argument("config", type=Path, help="staged OpenCode JSONC configuration path")
    parser.add_argument("patterns", nargs="+", help="external-directory patterns to allow")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        validate_patterns(args.patterns)
        inject(args.config, args.patterns)
    except (InjectionError, OSError, UnicodeError, RecursionError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
