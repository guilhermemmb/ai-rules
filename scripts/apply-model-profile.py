#!/usr/bin/env python3
"""Apply a versioned model profile to oh-my-opencode-slim.json.

Schema version 1: each agent entry is {model, optional variant} inside an
'agents' mapping.  The top-level mapping carries a 'version' key.

Application resolves every profile agent exactly once across the active
OMO preset (config.preset) and custom agents (config.agents).  An agent
found in neither location is an error.  An agent found in both is an
error (duplicate resolution).

A profile entry that omits variant leaves the agent's existing variant
unchanged.
"""
import sys
import json
import yaml
import os

PROFILE_SCHEMA_VERSION = 1


def _validate_profile(profile_path, profile):
    """Raise ValueError if the loaded profile fails schema checks."""
    if not isinstance(profile, dict):
        raise ValueError("profile must be a mapping")
    version = profile.get("version")
    if version != PROFILE_SCHEMA_VERSION:
        raise ValueError(
            f"profile schema version must be {PROFILE_SCHEMA_VERSION}, got {version!r}"
        )
    agents = profile.get("agents")
    if not isinstance(agents, dict):
        raise ValueError("profile.agents must be a mapping")
    for agent_id, spec in agents.items():
        if not isinstance(agent_id, str) or not agent_id:
            raise ValueError(f"profile agent key must be a non-empty string, got {agent_id!r}")
        if not isinstance(spec, dict):
            raise ValueError(f"profile.agents.{agent_id} must be a mapping")
        model = spec.get("model")
        if not isinstance(model, str) or not model:
            raise ValueError(f"profile.agents.{agent_id}.model must be a non-empty string")
        if "variant" in spec:
            variant = spec["variant"]
            if not isinstance(variant, str) or not variant:
                raise ValueError(
                    f"profile.agents.{agent_id}.variant must be a non-empty string "
                    f"or absent, got {variant!r}"
                )


def patch_config(src_dir, profile_name):
    profile_path = os.path.join(src_dir, "profiles", "models", f"{profile_name}.yml")
    config_path = os.path.join(src_dir, "oh-my-opencode-slim.json")

    if not os.path.exists(profile_path):
        print(f"  \u274c Model profile not found: {profile_name} (expected {profile_path})")
        sys.exit(1)

    print(f"  \U0001f3ad Applying model profile: {profile_name}...")

    with open(profile_path, 'r') as f:
        profile = yaml.safe_load(f)

    _validate_profile(profile_path, profile)
    agents = profile["agents"]

    with open(config_path, 'r') as f:
        config = json.load(f)

    applied = 0

    # Resolve active preset (not hard-coded bifrost)
    preset_name = config.get("preset", "bifrost")
    presets = config.get("presets")
    preset_agents = (
        presets.get(preset_name)
        if isinstance(presets, dict) and isinstance(presets.get(preset_name), dict)
        else None
    )
    custom_agents = config.get("agents") if isinstance(config.get("agents"), dict) else None

    # Build a combined lookup describing where each OMO agent lives:
    # agent_id -> ("preset", dict) or ("custom", dict) or None if missing.
    agent_locations: dict[str, tuple[str, dict]] = {}
    agent_both: list[str] = []
    if preset_agents:
        for agent_id in preset_agents:
            if agent_id in agent_locations:
                agent_both.append(agent_id)
            agent_locations[agent_id] = ("preset", preset_agents)
    if custom_agents:
        for agent_id in custom_agents:
            if agent_id in agent_locations:
                agent_both.append(agent_id)
            agent_locations[agent_id] = ("custom", custom_agents)

    if agent_both:
        raise ValueError(
            f"profile agent(s) found in both active preset {preset_name!r} "
            f"and custom agents: {', '.join(sorted(agent_both))}"
        )

    for agent_id, spec in agents.items():
        location = agent_locations.get(agent_id)
        if location is None:
            raise ValueError(
                f"profile agent {agent_id!r} not found in active preset "
                f"{preset_name!r} or custom agents"
            )
        _, target = location
        target[agent_id]["model"] = spec["model"]
        if "variant" in spec:
            target[agent_id]["variant"] = spec["variant"]
        applied += 1

    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
        f.write("\n")

    print(f"  \u2705 Applied profile to oh-my-opencode-slim.json ({applied} agent entries)")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: apply-model-profile.py <src_dir> <profile_name>")
        sys.exit(1)
    patch_config(sys.argv[1], sys.argv[2])