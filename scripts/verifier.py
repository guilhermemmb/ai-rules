"""Verify deployed config: JSON validity, agent restrictions, etc."""
import json
from pathlib import Path


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


def verify_agents_block(settings_file, logger):
    """Check agents block exists and has valid structure."""
    logger.debug(f"Verifying agents block in {settings_file}")

    try:
        with open(settings_file) as f:
            settings = json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        logger.error(f"Failed to load settings: {e}")
        return False

    if "agents" not in settings:
        logger.error("No agents block in settings.json")
        return False

    agents = settings["agents"]
    if not isinstance(agents, dict):
        logger.error("agents block is not a dict")
        return False

    logger.success(f"Agents block valid ({len(agents)} agents)")
    return True


def verify_main_agent_restrictions(settings_file, logger):
    """Verify main agent has no restricted MCPs/tools."""
    logger.debug("Verifying main agent restrictions")

    try:
        with open(settings_file) as f:
            settings = json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        logger.error(f"Failed to load settings: {e}")
        return False

    if "agents" not in settings or "main" not in settings["agents"]:
        logger.debug("main agent not in settings (OK)")
        return True

    main_agent = settings["agents"]["main"]
    restricted_mcps = ["cortex", "notion", "linear", "chrome-devtools", "superpowers-chrome", "sentry"]
    restricted_tools = []

    # Check MCPs
    if "mcps" in main_agent:
        mcps = main_agent["mcps"]
        found_restricted = [m for m in mcps if m in restricted_mcps]
        if found_restricted:
            logger.error(f"main agent has restricted MCPs: {', '.join(found_restricted)}")
            return False

    # Check tools (if needed in future)
    if "tools" in main_agent:
        tools = main_agent["tools"]
        found_restricted = [t for t in tools if t in restricted_tools]
        if found_restricted:
            logger.error(f"main agent has restricted tools: {', '.join(found_restricted)}")
            return False

    logger.success("main agent has no restricted access")
    return True


def verify_deployment(agents_json, settings_file, logger):
    """Run all verifications."""
    logger.info("Starting verification")

    checks = [
        ("agents config JSON", lambda: verify_json(agents_json, logger)),
        ("settings JSON", lambda: verify_json(settings_file, logger)),
        ("agents block structure", lambda: verify_agents_block(settings_file, logger)),
        ("main agent restrictions", lambda: verify_main_agent_restrictions(settings_file, logger)),
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
