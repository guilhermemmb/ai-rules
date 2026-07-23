"""Build agents config from agents/*.md files."""
import sys
import argparse
from pathlib import Path

from logger import Logger
from agent_config import build_agents_config, write_agents_config


def main():
    """
    Build agents config from agents/*.md files.

    Usage: python scripts/build_agents.py [--output /path/to/config.json] [--verbose]
    """
    parser = argparse.ArgumentParser(description="Build agent config from agents/*.md")
    parser.add_argument(
        "--output",
        default="/tmp/agents-config.json",
        help="Output config file (default: /tmp/agents-config.json)",
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

    logger.info("Done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
