"""Patch ~/.claude/settings.json with agents config."""
import json
import shutil
from pathlib import Path


def patch_settings(settings_file, agents_config, logger):
    """
    Merge agents_config into settings_file.

    Creates backup before modifying.
    Validates JSON before/after patch.

    Returns True on success, False otherwise.
    """
    logger.debug(f"Patching {settings_file} with agents config")

    settings_path = Path(settings_file)
    if not settings_path.exists():
        logger.error(f"Settings file not found: {settings_file}")
        return False

    # Load existing settings
    try:
        with open(settings_path) as f:
            settings = json.load(f)
        logger.debug("Loaded existing settings.json")
    except (IOError, json.JSONDecodeError) as e:
        logger.error(f"Failed to load settings: {e}")
        return False

    # Create backup
    backup_path = f"{settings_file}.backup"
    try:
        shutil.copy(settings_path, backup_path)
        logger.debug(f"Created backup at {backup_path}")
    except IOError as e:
        logger.warn(f"Failed to create backup: {e}")

    # Initialize agents block if missing
    if "agents" not in settings:
        settings["agents"] = {}

    # Merge main agent if present
    if "main" in agents_config:
        settings["agents"]["main"] = agents_config["main"]
        logger.debug("Merged main agent into settings")

    # Merge subagents
    if "agents" in agents_config:
        for agent_name, agent_config in agents_config["agents"].items():
            settings["agents"][agent_name] = agent_config
        logger.debug("Merged subagents into settings")

    # Validate result
    try:
        json.dumps(settings)
    except (TypeError, ValueError) as e:
        logger.error(f"Invalid JSON after patch: {e}")
        return False

    # Write patched settings
    try:
        with open(settings_path, "w") as f:
            json.dump(settings, f, indent=2)
        logger.success(f"Patched settings at {settings_file}")
        return True
    except IOError as e:
        logger.error(f"Failed to write settings: {e}")
        return False
