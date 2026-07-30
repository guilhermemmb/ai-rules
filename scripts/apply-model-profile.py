#!/usr/bin/env python3
import sys
import json
import yaml
import os

def patch_config(src_dir, profile_name):
    profile_path = os.path.join(src_dir, "profiles", "models", f"{profile_name}.yml")
    config_path = os.path.join(src_dir, "oh-my-opencode-slim.json")

    if not os.path.exists(profile_path):
        print(f"  ❌ Model profile not found: {profile_name} (expected {profile_path})")
        sys.exit(1)

    print(f"  🎭 Applying model profile: {profile_name}...")

    with open(profile_path, 'r') as f:
        profile = yaml.safe_load(f)

    with open(config_path, 'r') as f:
        config = json.load(f)

    # Update presets (bifrost)
    if "presets" in config and "bifrost" in config["presets"]:
        b = config["presets"]["bifrost"]
        for agent_id, model in profile.items():
            if agent_id in b:
                b[agent_id]["model"] = model
            elif agent_id == "orchestrator":
                # Special case: some presets might have specific orchestrator fields
                if "orchestrator" in b:
                    b["orchestrator"]["model"] = model

    # Update agents
    if "agents" in config:
        a = config["agents"]
        for agent_id, model in profile.items():
            if agent_id in a:
                a[agent_id]["model"] = model
            # Special logic for sage often using orchestrator's intelligence tier
            if agent_id == "orchestrator" and "sage" in a:
                # Only fallback if sage not explicitly in profile
                if "sage" not in profile:
                    a["sage"]["model"] = model

    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"  ✅ Applied profile to oh-my-opencode-slim.json")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: apply-model-profile.py <src_dir> <profile_name>")
        sys.exit(1)
    patch_config(sys.argv[1], sys.argv[2])
