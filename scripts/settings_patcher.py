"""Patch ~/.claude/settings.json: remove non-official agents block, sync main model."""
import json
import re
import shutil
from pathlib import Path

import yaml


def _get_main_model(agents_dir):
    """Read model: from agents/main.md YAML frontmatter. Returns None if not found."""
    main_file = Path(agents_dir) / "main.md"
    if not main_file.exists():
        return None
    try:
        content = main_file.read_text()
        match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if not match:
            return None
        fm = yaml.safe_load(match.group(1)) or {}
        return fm.get("model")
    except Exception:
        return None


def patch_settings(settings_file, agents_config, logger, agents_dir=None):
    """
    Remove the custom agents block from settings.json and sync main agent model.

    Agent MCP access is now controlled via mcpServers: in ~/.claude/agents/*.md
    frontmatter (official Claude Code format). The agents block in settings.json
    was a non-official custom format.
    """
    logger.debug(f"Patching {settings_file}")

    settings_path = Path(settings_file)
    if not settings_path.exists():
        logger.error(f"Settings file not found: {settings_file}")
        return False

    try:
        with open(settings_path) as f:
            settings = json.load(f)
        logger.debug("Loaded existing settings.json")
    except (IOError, json.JSONDecodeError) as e:
        logger.error(f"Failed to load settings: {e}")
        return False

    changed = False

    if "agents" in settings:
        backup_path = f"{settings_file}.backup"
        try:
            shutil.copy(settings_path, backup_path)
            logger.debug(f"Created backup at {backup_path}")
        except IOError as e:
            logger.warn(f"Failed to create backup: {e}")
        del settings["agents"]
        logger.debug("Removed agents block from settings")
        changed = True
    else:
        logger.debug("No agents block in settings.json — nothing to remove")

    if agents_dir:
        model = _get_main_model(agents_dir)
        if model and settings.get("model") != model:
            settings["model"] = model
            logger.debug(f"Synced main model: {model}")
            changed = True

    if not changed:
        logger.debug("No changes to settings.json")
        return True

    try:
        with open(settings_path, "w") as f:
            json.dump(settings, f, indent=2)
        logger.success(f"Patched settings at {settings_file}")
        return True
    except IOError as e:
        logger.error(f"Failed to write settings: {e}")
        return False
