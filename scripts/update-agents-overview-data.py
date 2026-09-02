#!/usr/bin/env python3
import json
import os
import tempfile

import yaml
from yaml.events import AliasEvent
from yaml.nodes import MappingNode, ScalarNode, SequenceNode

GENERATED_SECTIONS = ("profiles", "model_names", "avatars")


def _make_hashable(value):
    if isinstance(value, dict):
        return (
            "mapping",
            frozenset(
                (_make_hashable(key), _make_hashable(item))
                for key, item in value.items()
            ),
        )
    if isinstance(value, list):
        return ("sequence", tuple(_make_hashable(item) for item in value))
    if isinstance(value, set):
        return ("set", frozenset(_make_hashable(item) for item in value))
    try:
        hash(value)
    except TypeError:
        return ("unhashable", type(value), repr(value))
    return (type(value), value)


def _make_semantic_key(loader, key_node):
    return (
        key_node.tag,
        _make_hashable(loader.construct_object(key_node, deep=True)),
    )


def _get_top_level_section_nodes(text):
    document = yaml.compose(text, Loader=yaml.SafeLoader)
    if not isinstance(document, MappingNode):
        raise TypeError("data.yaml must contain a top-level mapping")

    loader = yaml.SafeLoader(text)
    sections = []
    try:
        for key_node, value_node in document.value:
            sections.append(
                (
                    key_node.value if isinstance(key_node, ScalarNode) else None,
                    key_node.start_mark.index,
                    key_node,
                    value_node,
                    _make_semantic_key(loader, key_node),
                )
            )
    finally:
        loader.dispose()
    return sections


def get_top_level_sections(text):
    return [
        (name, start)
        for name, start, _key_node, _value_node, _semantic_key in _get_top_level_section_nodes(
            text
        )
    ]


def _section_for_position(sections, position):
    for section in reversed(sections):
        if section[1] <= position:
            return section
    return None


def _validate_anchor_boundaries(text, sections):
    anchors = {}
    aliases = []
    for event in yaml.parse(text, Loader=yaml.SafeLoader):
        section = _section_for_position(sections, event.start_mark.index)
        if isinstance(event, AliasEvent):
            aliases.append((event.anchor, section))
        elif getattr(event, "anchor", None):
            anchors.setdefault(event.anchor, []).append(section)

    for anchor, alias_section in aliases:
        for anchor_section in anchors.get(anchor, []):
            if not anchor_section or not alias_section:
                continue
            anchor_name = anchor_section[0]
            alias_name = alias_section[0]
            if anchor_name == alias_name:
                continue
            if anchor_name in GENERATED_SECTIONS or alias_name in GENERATED_SECTIONS:
                anchor_label = anchor_name or "<non-scalar key>"
                alias_label = alias_name or "<non-scalar key>"
                raise ValueError(
                    f"cannot replace generated YAML section: anchor &{anchor} in "
                    f"section {anchor_label} is referenced by alias *{anchor} "
                    f"in section {alias_label}"
                )


def _node_content_end(node):
    if isinstance(node, (MappingNode, SequenceNode)) and not node.flow_style:
        child_ends = []
        if isinstance(node, MappingNode):
            for key_node, value_node in node.value:
                child_ends.extend(
                    (
                        _node_content_end(key_node),
                        _node_content_end(value_node),
                    )
                )
        else:
            child_ends.extend(_node_content_end(item) for item in node.value)
        return max([node.start_mark.index] + child_ends)
    return node.end_mark.index


def _section_body_end(text, value_node):
    end = _node_content_end(value_node)
    if text.startswith("\r\n", end):
        return end + 2
    if text.startswith("\n", end):
        return end + 1
    return end


def _header_comment(text, key_node):
    line_start = text.rfind("\n", 0, key_node.start_mark.index) + 1
    line_end = text.find("\n", key_node.start_mark.index)
    if line_end == -1:
        line_end = len(text)
    line = text[line_start:line_end].rstrip("\r")

    quote = None
    escaped = False
    comment_index = None
    index = 0
    while index < len(line):
        character = line[index]
        if quote == '"':
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quote = None
        elif quote == "'":
            if character == "'":
                if index + 1 < len(line) and line[index + 1] == "'":
                    index += 1
                else:
                    quote = None
        elif character in ('"', "'"):
            quote = character
        elif character == "#" and (index == 0 or line[index - 1].isspace()):
            comment_index = index
            break
        index += 1

    if comment_index is None:
        return None

    key_end = key_node.end_mark.index - line_start
    colon_index = line.find(":", max(key_end, 0), comment_index)
    before_comment = line[colon_index + 1 : comment_index] if colon_index != -1 else ""
    spacing = before_comment[len(before_comment.rstrip(" \t")) :]
    return (spacing or " ") + line[comment_index:]


def _serialize_generated_section(text, key_node, name, value):
    serialized = yaml.safe_dump(
        {name: value},
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
        width=1000,
    )
    newline = "\r\n" if "\r\n" in text else "\n"
    if newline != "\n":
        serialized = serialized.replace("\n", newline)

    comment = _header_comment(text, key_node)
    if comment:
        first_line_end = serialized.find(newline)
        serialized = serialized[:first_line_end] + comment + serialized[first_line_end:]
    return serialized


def _validate_mapping_keys(node, loader, path="root", visited=None):
    if visited is None:
        visited = set()
    if id(node) in visited:
        return
    visited.add(id(node))

    if isinstance(node, MappingNode):
        seen = {}
        for key_node, value_node in node.value:
            semantic_key = _make_semantic_key(loader, key_node)
            key_name = (
                key_node.value
                if isinstance(key_node, ScalarNode)
                else "<non-scalar key>"
            )
            if semantic_key in seen:
                raise ValueError(
                    "generated data.yaml candidate contains duplicate mapping "
                    f"key {key_name!r} at {path}"
                )
            seen[semantic_key] = key_node.start_mark.index
            _validate_mapping_keys(key_node, loader, path, visited)
            _validate_mapping_keys(
                value_node,
                loader,
                f"{path}.{key_name}",
                visited,
            )
    elif isinstance(node, SequenceNode):
        for index, item in enumerate(node.value):
            _validate_mapping_keys(item, loader, f"{path}[{index}]", visited)


def _validate_generated_section_schemas(data):
    for section_name in GENERATED_SECTIONS:
        if not isinstance(data.get(section_name), dict):
            raise TypeError(
                f"generated data.yaml section {section_name!r} must be a mapping"
            )

    for profile_name, profile in data["profiles"].items():
        if not isinstance(profile_name, str) or not isinstance(profile, dict):
            raise TypeError("generated data.yaml profiles must map names to mappings")
        if any(
            not isinstance(agent_name, str) or not isinstance(model, str)
            for agent_name, model in profile.items()
        ):
            raise TypeError(
                f"generated data.yaml profile {profile_name!r} must map agents to model names"
            )

    for model_id, model_name in data["model_names"].items():
        if not isinstance(model_id, str) or not isinstance(model_name, str):
            raise TypeError(
                "generated data.yaml model_names must map model IDs to names"
            )

    for agent_name, avatar in data["avatars"].items():
        if not isinstance(agent_name, str) or not isinstance(avatar, str):
            raise TypeError(
                "generated data.yaml avatars must map agent names to strings"
            )


def _validate_candidate_yaml(text):
    try:
        document = yaml.compose(text, Loader=yaml.SafeLoader)
        if document is None:
            raise TypeError("generated data.yaml candidate must contain a document")
        loader = yaml.SafeLoader(text)
        try:
            _validate_mapping_keys(document, loader)
        finally:
            loader.dispose()
        candidate_data = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise ValueError(
            "generated data.yaml candidate is invalid YAML: " + str(error)
        ) from error

    if not isinstance(candidate_data, dict):
        raise TypeError(
            "generated data.yaml candidate must contain a top-level mapping"
        )
    _validate_generated_section_schemas(candidate_data)


def get_model_names(opencode_path):
    names = {}
    if not os.path.exists(opencode_path):
        return names

    with open(opencode_path, "r") as f:
        data = json.load(f)

    providers = data.get("provider", {})
    for p_id in sorted(providers):
        p_info = providers[p_id]
        models = p_info.get("models", {})
        for m_id in sorted(models):
            m_info = models[m_id]
            full_id = f"{p_id}/{m_id}"
            # Extract a friendly name
            name = m_info.get("name", m_id)
            # Prettify if it looks like a path
            if "/" in name:
                name = name.split("/")[-1]
            name = name.replace("-", " ").replace("_", " ").title()
            # Special case for GPT models
            if "Gpt" in name:
                name = name.replace("Gpt", "GPT")
            names[full_id] = name
    return names


def replace_generated_sections(data_yaml_path, generated_sections):
    with open(data_yaml_path, "r", encoding="utf-8", newline="") as f:
        text = f.read()

    section_positions = {}
    semantic_positions = {}
    semantic_names = {}
    section_ends = {}
    section_headers = {}
    top_level_sections = _get_top_level_section_nodes(text)
    for name, start, key_node, value_node, semantic_key in top_level_sections:
        semantic_positions.setdefault(semantic_key, []).append(start)
        semantic_names.setdefault(
            semantic_key,
            name if name is not None else "<non-scalar key>",
        )
        section_ends[start] = _section_body_end(text, value_node)
        section_headers[start] = key_node
        if name is not None:
            section_positions.setdefault(name, []).append(start)

    missing = [name for name in GENERATED_SECTIONS if name not in section_positions]
    if missing:
        raise ValueError(
            "data.yaml is missing expected generated top-level section(s): "
            + ", ".join(missing)
        )

    duplicate = [
        name for name in GENERATED_SECTIONS if len(section_positions[name]) != 1
    ]
    if duplicate:
        raise ValueError(
            "data.yaml must contain exactly one generated top-level section: "
            + ", ".join(duplicate)
        )

    duplicate_top_level = [
        semantic_names[semantic_key]
        for semantic_key, positions in semantic_positions.items()
        if len(positions) > 1
    ]
    if duplicate_top_level:
        raise ValueError(
            "data.yaml must contain unique top-level sections: "
            + ", ".join(duplicate_top_level)
        )

    _validate_anchor_boundaries(text, top_level_sections)

    replacements = []
    for name in GENERATED_SECTIONS:
        start = section_positions[name][0]
        end = section_ends[start]
        serialized = _serialize_generated_section(
            text,
            key_node=section_headers[start],
            name=name,
            value=generated_sections[name],
        )
        replacements.append((start, end, serialized))

    for start, end, serialized in sorted(replacements, reverse=True):
        text = text[:start] + serialized + text[end:]

    _validate_candidate_yaml(text)

    directory = os.path.dirname(os.path.abspath(data_yaml_path))
    prefix = "." + os.path.basename(data_yaml_path) + "."
    original_mode = os.stat(data_yaml_path).st_mode
    file_descriptor, temporary_path = tempfile.mkstemp(
        dir=directory,
        prefix=prefix,
    )
    try:
        os.chmod(temporary_path, original_mode & 0o7777)
        with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="") as f:
            file_descriptor = None
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary_path, data_yaml_path)
    finally:
        if file_descriptor is not None:
            os.close(file_descriptor)
        try:
            os.unlink(temporary_path)
        except OSError:
            pass


def main():
    src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_yaml_path = os.path.join(src_dir, "agents-overview", "data.yaml")
    profiles_dir = os.path.join(src_dir, "profiles", "models")
    opencode_path = os.path.join(src_dir, "opencode.json")

    print(f"🔄 Updating {data_yaml_path}...")

    # 1. Load existing data.yaml
    with open(data_yaml_path, "r") as f:
        data = yaml.safe_load(f)

    # 2. Load profiles (versioned schema: agents.{id}.{model, variant})
    profiles = {}
    for filename in sorted(os.listdir(profiles_dir)):
        if filename.endswith(".yml"):
            name = filename[:-4]
            with open(os.path.join(profiles_dir, filename), "r") as f:
                raw = yaml.safe_load(f)
            # Emit the existing flat shape for data.yaml compatibility:
            # agent_id -> model string.  The full {model, variant} spec
            # is the source of truth in the profile files.
            if isinstance(raw, dict) and isinstance(raw.get("agents"), dict):
                profiles[name] = {
                    agent_id: spec.get("model", "")
                    for agent_id, spec in raw["agents"].items()
                    if isinstance(spec, dict)
                }

    # 3. Get model names from opencode.json
    model_names = get_model_names(opencode_path)

    # 4. Define avatars (moved from JS)
    avatars = {
        "orchestrator": "🏛️",
        "oracle": "🔮",
        "explorer": "🧭",
        "librarian": "📚",
        "designer": "🎨",
        "fixer": "🔧",
        "observer": "👁️",
        "navigator": "🌐",
        "detective": "🔍",
        "sage": "🧠",
        "reviewer": "⚖️",
        "reviewer-security": "🔒",
        "reviewer-performance": "⚡",
        "reviewer-data-integrity": "🛡️",
        "reviewer-code": "💻",
        "reviewer-comments": "💬",
        "reviewer-test": "🧪",
        "reviewer-errors": "🚨",
        "reviewer-types": "🧩",
        "reviewer-simplifier": "✨",
        "reviewer-accessibility": "♿",
    }

    # 5. Validate the existing document and replace only generated sections.
    if not isinstance(data, dict):
        raise TypeError("data.yaml must contain a top-level mapping")
    missing = [name for name in GENERATED_SECTIONS if name not in data]
    if missing:
        raise ValueError(
            "data.yaml is missing expected generated section(s): " + ", ".join(missing)
        )
    replace_generated_sections(
        data_yaml_path,
        {
            "profiles": profiles,
            "model_names": model_names,
            "avatars": avatars,
        },
    )

    print("✅ data.yaml updated with profiles, model names, and avatars.")


if __name__ == "__main__":
    main()
