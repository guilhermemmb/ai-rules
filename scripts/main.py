"""Unified deployment orchestrator: build agents → rulesync → patch mcpServers → verify."""
import sys
import argparse
from pathlib import Path

from logger import Logger
from agent_config import build_agents_config, write_agents_config
from build_agents import deploy_to_agents_dir
from verifier import verify_deployment
from rulesync import run_rulesync


def main():
    """
    Orchestrate deployment: build config → rulesync → deploy mcpServers → verify.

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

    verbosity = 2 if args.verbose else (3 if args.quiet else 1)
    logger = Logger(verbosity=verbosity)

    logger.info("Deployment starting")

    script_dir = Path(__file__).parent.parent
    subagents_dir = script_dir / ".rulesync" / "subagents"
    settings_file = Path.home() / ".claude" / "settings.json"
    claude_agents_dir = Path.home() / ".claude" / "agents"

    # Step 1: Build agents config
    logger.info("Step 1: Building agents config")
    config = build_agents_config(str(subagents_dir), logger, subagents_dir=str(subagents_dir))
    if not config:
        logger.error("Failed to build agents config")
        return 1

    if not write_agents_config(config, args.output, logger):
        logger.error("Failed to write agents config")
        return 1

    # Step 2: Distribute rules via rulesync (deploys subagents + main to ~/.claude/agents/)
    logger.info("Step 2: Distributing rules via rulesync")
    if not run_rulesync(str(script_dir), logger):
        logger.warn("rulesync failed (continuing anyway)")

    # Step 3: Patch mcpServers into ~/.claude/agents/ (rulesync may not set all)
    logger.info("Step 3: Deploying mcpServers to ~/.claude/agents/")
    if not deploy_to_agents_dir(config, str(claude_agents_dir), logger):
        logger.error("Failed to deploy to ~/.claude/agents/")
        return 1

    # Step 4: Verify
    logger.info("Step 4: Verifying deployment")
    if not verify_deployment(args.output, str(settings_file), logger):
        logger.error("Verification failed")
        return 1

    logger.success("Deployment complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
