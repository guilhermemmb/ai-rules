"""Build agents config from agents/*.md files and deploy to ~/.claude/agents/."""
import sys
import re
import json
import argparse
from pathlib import Path

import yaml

from logger import Logger
from agent_config import build_agents_config, write_agents_config


def _update_frontmatter_mcpservers(content, mcpServers):
    """Replace or insert mcpServers and mcps fields in YAML frontmatter string."""
    match = re.match(r"^(---\n)(.*?)(\n---)(.*)", content, re.DOTALL)
    if not match:
        return content

    pre, fm_raw, sep, body = match.groups()
    fm = yaml.safe_load(fm_raw) or {}

    # Remove both to re-append as inline lists (avoids YAML anchors)
    fm.pop("mcps", None)
    fm.pop("mcpServers", None)

    base_fm = yaml.dump(fm, default_flow_style=False).rstrip()
    inline = "[" + ", ".join(mcpServers) + "]"
    new_fm = base_fm + f"\nmcpServers: {inline}\nmcps: {inline}"

    return f"{pre}{new_fm}{sep}{body}"


def deploy_to_agents_dir(config, agents_dir, logger):
    """
    Patch mcpServers into ~/.claude/agents/<name>.md files.

    Preserves existing body content. Creates file from source if missing.
    Skips main agent (not a subagent).
    """
    agents_path = Path(agents_dir)
    agents_path.mkdir(parents=True, exist_ok=True)

    if "agents" not in config:
        logger.warn("No subagents in config, nothing to deploy")
        return True

    success = True
    for name, agent_config in config["agents"].items():
        mcpServers = agent_config.get("mcpServers", [])
        target = agents_path / f"{name}.md"

        if target.exists():
            try:
                content = target.read_text()
                updated = _update_frontmatter_mcpservers(content, mcpServers)
                target.write_text(updated)
                logger.success(f"Patched mcpServers in {target.name}")
            except Exception as e:
                logger.error(f"Failed to patch {target.name}: {e}")
                success = False
        else:
            logger.warn(f"~/.claude/agents/{name}.md not found — skipping (create it manually)")

    return success


def main():
    """
    Build agents config from agents/*.md files and deploy mcpServers to ~/.claude/agents/.

    Usage: python scripts/build_agents.py [--output /path/to/config.json] [--verbose] [--deploy]
    """
    parser = argparse.ArgumentParser(description="Build agent config from agents/*.md")
    parser.add_argument(
        "--output",
        default="/tmp/agents-config.json",
        help="Output config file (default: /tmp/agents-config.json)",
    )
    parser.add_argument(
        "--deploy",
        action="store_true",
        help="Deploy mcpServers into ~/.claude/agents/*.md files",
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

    logger.info("Building agents config")

    script_dir = Path(__file__).parent.parent
    agents_dir = script_dir / "agents"

    config = build_agents_config(str(agents_dir), logger)
    if not config:
        logger.error("Failed to build agents config")
        return 1

    if not write_agents_config(config, args.output, logger):
        logger.error("Failed to write agents config")
        return 1

    if args.deploy:
        claude_agents_dir = Path.home() / ".claude" / "agents"
        if not deploy_to_agents_dir(config, str(claude_agents_dir), logger):
            logger.error("Failed to deploy agents")
            return 1

    logger.info("Done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
