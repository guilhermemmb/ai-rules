"""Build agents config from agents/*.md files."""
import sys
import json
import argparse
from pathlib import Path

from logger import Logger
from agent_config import build_agents_config, write_agents_config


def merge_agents_into_settings(config, settings_file, logger):
    """
    Merge agents config into .claude/settings.json.

    Preserves existing settings, updates agents.main and agents.* subagents.
    """
    settings_path = Path(settings_file)

    # Load existing settings
    try:
        with open(settings_path) as f:
            settings = json.load(f)
        logger.debug(f"Loaded settings from {settings_file}")
    except FileNotFoundError:
        logger.warn(f"Settings file not found: {settings_file}, creating new")
        settings = {}
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in {settings_file}: {e}")
        return False

    # Initialize agents section if missing
    if "agents" not in settings:
        settings["agents"] = {}

    # Merge main agent if present
    if "main" in config:
        settings["agents"]["main"] = config["main"]
        logger.debug("Merged main agent into settings")

    # Merge subagents if present
    if "agents" in config:
        for agent_name, agent_config in config["agents"].items():
            settings["agents"][agent_name] = agent_config
            logger.debug(f"Merged agent '{agent_name}' into settings")

    # Write back
    try:
        with open(settings_path, "w") as f:
            json.dump(settings, f, indent=2)
        logger.success(f"Updated settings: {settings_file}")
        return True
    except IOError as e:
        logger.error(f"Failed to write settings: {e}")
        return False


def main():
    """
    Build agents config from agents/*.md files.

    Usage: python scripts/build_agents.py [--output /path/to/config.json] [--verbose] [--sync-settings]
    """
    parser = argparse.ArgumentParser(description="Build agent config from agents/*.md")
    parser.add_argument(
        "--output",
        default="/tmp/agents-config.json",
        help="Output config file (default: /tmp/agents-config.json)",
    )
    parser.add_argument(
        "--sync-settings",
        action="store_true",
        help="Sync agents config into ~/.claude/settings.json",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only show errors",
    )

    args = parser.parse_args()

    # Initialize logger
    verbosity = 2 if args.verbose else (3 if args.quiet else 1)
    logger = Logger(verbosity=verbosity)

    logger.info("Building agents config")

    # Determine agents directory
    script_dir = Path(__file__).parent.parent
    agents_dir = script_dir / "agents"

    # Build config
    config = build_agents_config(str(agents_dir), logger)
    if not config:
        logger.error("Failed to build agents config")
        return 1

    # Write to file
    if not write_agents_config(config, args.output, logger):
        logger.error("Failed to write agents config")
        return 1

    # Sync to settings if requested
    if args.sync_settings:
        settings_file = Path.home() / ".claude" / "settings.json"
        if not merge_agents_into_settings(config, str(settings_file), logger):
            logger.error("Failed to sync agents into settings")
            return 1

    logger.info("Done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
