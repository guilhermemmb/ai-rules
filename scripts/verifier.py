"""Verify deployed config: JSON validity, agent files, mcpServers restrictions."""
import json
import re
from pathlib import Path

import yaml


def verify_json(filepath, logger):
    """Validate JSON file."""
    logger.debug(f"Validating JSON: {filepath}")

    if not Path(filepath).exists():
        logger.error(f"File not found: {filepath}")
        return False

    try:
        with open(filepath) as f:
            json.load(f)
        logger.success(f"JSON valid: {filepath}")
        return True
    except (IOError, json.JSONDecodeError) as e:
        logger.error(f"Invalid JSON in {filepath}: {e}")
        return False


def _parse_frontmatter(filepath):
    """Return parsed YAML frontmatter dict from a .md file, or empty dict."""
    try:
        content = Path(filepath).read_text()
    except IOError:
        return {}

    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}

    try:
        return yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return {}


def verify_agents_dir(agents_config, claude_agents_dir, logger):
    """Check each subagent in config has a matching file in ~/.claude/agents/."""
    logger.debug(f"Verifying agents in {claude_agents_dir}")

    agents_path = Path(claude_agents_dir)
    if not agents_path.exists():
        logger.error(f"~/.claude/agents/ directory not found: {claude_agents_dir}")
        return False

    if "agents" not in agents_config:
        logger.debug("No subagents in config — skipping agents dir check")
        return True

    missing = []
    for name in agents_config["agents"]:
        target = agents_path / f"{name}.md"
        if not target.exists():
            missing.append(name)

    if missing:
        logger.warn(f"Missing agent files in ~/.claude/agents/: {', '.join(missing)}")
    else:
        logger.success(f"All {len(agents_config['agents'])} agent files present")

    return True


def verify_mcpservers_in_agents_dir(agents_config, claude_agents_dir, logger):
    """Check mcpServers frontmatter is set correctly in ~/.claude/agents/*.md."""
    logger.debug("Verifying mcpServers in agent files")

    agents_path = Path(claude_agents_dir)
    if "agents" not in agents_config:
        return True

    restricted_mcps = {"cortex", "notion", "linear", "chrome-devtools", "superpowers-chrome", "sentry", "datadog", "gcloud"}
    errors = []

    for name, config in agents_config["agents"].items():
        target = agents_path / f"{name}.md"
        if not target.exists():
            continue

        fm = _parse_frontmatter(str(target))
        deployed = set(fm.get("mcpServers", []))
        expected = set(config.get("mcpServers", []))

        if deployed != expected:
            errors.append(f"{name}: expected {sorted(expected)}, got {sorted(deployed)}")

    if errors:
        for e in errors:
            logger.warn(f"mcpServers mismatch: {e}")
    else:
        logger.success("All agent mcpServers match config")

    return True


def verify_no_agents_block_in_settings(settings_file, logger):
    """Confirm settings.json has no custom agents block."""
    logger.debug("Checking settings.json has no agents block")

    try:
        with open(settings_file) as f:
            settings = json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        logger.error(f"Failed to load settings: {e}")
        return False

    if "agents" in settings:
        logger.error("settings.json still has agents block — patch_settings may have failed")
        return False

    logger.success("settings.json has no agents block")
    return True


def verify_deployment(agents_json, settings_file, logger):
    """Run all verifications."""
    logger.info("Starting verification")

    claude_agents_dir = Path.home() / ".claude" / "agents"

    try:
        with open(agents_json) as f:
            agents_config = json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        logger.error(f"Failed to load agents config: {e}")
        return False

    checks = [
        ("agents config JSON", lambda: verify_json(agents_json, logger)),
        ("settings JSON", lambda: verify_json(settings_file, logger)),
        ("no agents block in settings", lambda: verify_no_agents_block_in_settings(settings_file, logger)),
        ("agent files in ~/.claude/agents/", lambda: verify_agents_dir(agents_config, str(claude_agents_dir), logger)),
        ("mcpServers in agent files", lambda: verify_mcpservers_in_agents_dir(agents_config, str(claude_agents_dir), logger)),
    ]

    passed = 0
    for name, check in checks:
        if check():
            passed += 1
        else:
            logger.warn(f"Check failed: {name}")

    if passed == len(checks):
        logger.success(f"All {len(checks)} verifications passed")
        return True
    else:
        logger.error(f"Verification failed: {passed}/{len(checks)} checks passed")
        return False
