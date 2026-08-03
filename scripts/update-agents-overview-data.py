#!/usr/bin/env python3
import os
import yaml
import json

def get_model_names(opencode_path):
    names = {}
    if not os.path.exists(opencode_path):
        return names
    
    with open(opencode_path, 'r') as f:
        data = json.load(f)
    
    providers = data.get('provider', {})
    for p_id, p_info in providers.items():
        models = p_info.get('models', {})
        for m_id, m_info in models.items():
            full_id = f"{p_id}/{m_id}"
            # Extract a friendly name
            name = m_info.get('name', m_id)
            # Prettify if it looks like a path
            if '/' in name:
                name = name.split('/')[-1]
            name = name.replace('-', ' ').replace('_', ' ').title()
            # Special case for GPT models
            if 'Gpt' in name:
                name = name.replace('Gpt', 'GPT')
            names[full_id] = name
    return names

def main():
    src_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_yaml_path = os.path.join(src_dir, "agents-overview", "data.yaml")
    profiles_dir = os.path.join(src_dir, "profiles", "models")
    opencode_path = os.path.join(src_dir, "opencode.json")

    print(f"🔄 Updating {data_yaml_path}...")

    # 1. Load existing data.yaml
    with open(data_yaml_path, 'r') as f:
        data = yaml.safe_load(f)

    # 2. Load profiles
    profiles = {}
    for filename in os.listdir(profiles_dir):
        if filename.endswith(".yml"):
            name = filename[:-4]
            with open(os.path.join(profiles_dir, filename), 'r') as f:
                profiles[name] = yaml.safe_load(f)

    # 3. Get model names from opencode.json
    model_names = get_model_names(opencode_path)

    # 4. Define avatars (moved from JS)
    avatars = {
        "orchestrator": "🏛️", "oracle": "🔮", "explorer": "🧭", "librarian": "📚",
        "designer": "🎨", "fixer": "🔧", "observer": "👁️", "navigator": "🌐",
        "detective": "🔍", "sage": "🧠", "reviewer": "⚖️"
    }

    # 5. Inject into data
    data['profiles'] = profiles
    data['model_names'] = model_names
    data['avatars'] = avatars

    # 6. Write back
    with open(data_yaml_path, 'w') as f:
        yaml.dump(data, f, sort_keys=False, allow_unicode=True)

    print("✅ data.yaml updated with profiles, model names, and avatars.")

if __name__ == "__main__":
    main()
