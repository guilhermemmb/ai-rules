"""Parse agent YAML frontmatter → JSON config."""
import json
import re
from pathlib import Path
import yaml


def parse_agent_file(filepath):
    """
    Parse single agent .md file.

    Supports two frontmatter formats:
    - Direct: mcpServers: [...]
    - Rulesync: claudecode: { mcpServers: [...] }

    Returns dict with name, tools, mcpServers or empty dict if invalid.
    """
    try:
        with open(filepath) as f:
            content = f.read()
    except IOError:
        return {}

    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}

    try:
        frontmatter = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return {}

    if not isinstance(frontmatter, dict):
        return {}

    if "name" not in frontmatter:
        return {}

    agent = {"name": frontmatter["name"]}

    tools = frontmatter.get("tools", [])
    agent["tools"] = tools if isinstance(tools, list) else []

    # Support direct mcpServers or nested claudecode.mcpServers (rulesync format)
    claudecode = frontmatter.get("claudecode", {}) or {}
    mcp_servers = frontmatter.get("mcpServers") or claudecode.get("mcpServers", [])
    agent["mcpServers"] = mcp_servers if isinstance(mcp_servers, list) else []

    return agent


def build_agents_config(agents_dir, logger, subagents_dir=None):
    """
    Parse agent .md files → agents config dict.

    Reads main.md from agents_dir.
    Reads subagents from subagents_dir (falls back to agents_dir).
    Skips: routing.md, README.md, statusline-setup.md

    Returns dict: {main: {...}, agents: {agent_name: {...}}}
    """
    logger.debug(f"Building agent config from {agents_dir}")

    agents_path = Path(agents_dir)
    if not agents_path.exists():
        logger.error(f"Agents directory not found: {agents_dir}")
        return {}

    subagents_path = Path(subagents_dir) if subagents_dir else agents_path
    if not subagents_path.exists():
        logger.error(f"Subagents directory not found: {subagents_dir}")
        return {}

    main_agent = {}
    main_file = agents_path / "main.md"
    if main_file.exists():
        main_agent = parse_agent_file(str(main_file))
        if main_agent:
            main_agent.pop("name", None)
            logger.debug("Parsed main agent")
        else:
            logger.warn("main.md exists but is invalid")

    agents = {}
    skip_files = {"main.md", "routing.md", "README.md", "statusline-setup.md"}

    for md_file in sorted(subagents_path.glob("*.md")):
        if md_file.name in skip_files:
            logger.debug(f"Skipping {md_file.name}")
            continue

        agent = parse_agent_file(str(md_file))
        if not agent:
            logger.debug(f"No valid agent in {md_file.name}")
            continue

        name = agent.pop("name")
        agents[name] = agent
        logger.debug(f"Parsed agent: {name}")

    config = {}
    if main_agent:
        config["main"] = main_agent
    if agents:
        config["agents"] = agents

    if not config:
        logger.warn("No agents found")
        return {}

    agent_count = len(agents) + (1 if main_agent else 0)
    logger.success(f"Built config for {agent_count} agents")
    return config


def write_agents_config(config, output_file, logger):
    """Write agents config to JSON file."""
    logger.debug(f"Writing agents config to {output_file}")

    try:
        with open(output_file, "w") as f:
            json.dump(config, f, indent=2)
        logger.success(f"Agent config written to {output_file}")
        return True
    except IOError as e:
        logger.error(f"Failed to write {output_file}: {e}")
        return False
