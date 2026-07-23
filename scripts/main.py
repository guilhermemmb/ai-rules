"""Unified deployment orchestrator: build agents → patch settings → verify."""
import sys
import argparse
from pathlib import Path

from logger import Logger
from agent_config import build_agents_config, write_agents_config
from settings_patcher import patch_settings
from verifier import verify_deployment
from rulesync import run_rulesync


def main():
    """
    Orchestrate deployment: build config → patch settings → verify → rulesync.

    Usage: python scripts/main.py [--verbose] [--quiet] [--output /path/to/config.json]
    """
    parser = argparse.ArgumentParser(description="Deploy agent config")
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

    logger.info("Deployment starting")

    # Directories
    script_dir = Path(__file__).parent.parent
    agents_dir = script_dir / "agents"
    settings_file = Path.home() / ".claude" / "settings.json"

    # Step 1: Build agents config
    logger.info("Step 1: Building agents config")
    config = build_agents_config(str(agents_dir), logger)
    if not config:
        logger.error("Failed to build agents config")
        return 1

    if not write_agents_config(config, args.output, logger):
        logger.error("Failed to write agents config")
        return 1

    # Step 2: Patch settings
    logger.info("Step 2: Patching settings")
    if not patch_settings(str(settings_file), config, logger):
        logger.error("Failed to patch settings")
        return 1

    # Step 3: Verify
    logger.info("Step 3: Verifying deployment")
    if not verify_deployment(args.output, str(settings_file), logger):
        logger.error("Verification failed")
        return 1

    # Step 4: Rulesync
    logger.info("Step 4: Distributing rules")
    if not run_rulesync(str(script_dir), logger):
        logger.warn("rulesync failed (continuing anyway)")

    logger.success("Deployment complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
