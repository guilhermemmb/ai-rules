#!/usr/bin/env python3
"""Focused tests for the versioned model-profile schema.

Coverage: schema rejection (version, agents, keys, model, variant),
invalid variants (null, empty, non-string), default and cost-efficient
profile application, missing-agent error, active-preset resolution,
omitted-variant preservation.
"""
import importlib.util
import json
import os
import sys
import tempfile
from pathlib import Path

import yaml

_HERE = Path(__file__).resolve().parent
_AMP_PATH = _HERE / "apply-model-profile.py"

_amp_spec = importlib.util.spec_from_file_location("apply_model_profile", _AMP_PATH)
_amp_module = importlib.util.module_from_spec(_amp_spec)
_amp_spec.loader.exec_module(_amp_module)

PROFILE_SCHEMA_VERSION: int = _amp_module.PROFILE_SCHEMA_VERSION
_validate_profile = _amp_module._validate_profile
_patch_config = _amp_module.patch_config


def _make_omo():
    """Return a minimal OMO-like config dict for patch testing."""
    return {
        "preset": "bifrost",
        "disabled_agents": [],
        "presets": {
            "bifrost": {
                "orchestrator": {"model": "bf-o/gpt-5.6-luna", "variant": "high"},
                "oracle": {"model": "bf-o/gpt-5.6-luna", "variant": "high"},
                "explorer": {
                    "model": "bf/huggingface/fireworks-ai/deepseek-ai/DeepSeek-V4-Flash",
                    "variant": "low",
                },
                "librarian": {
                    "model": "bf/huggingface/fireworks-ai/deepseek-ai/DeepSeek-V4-Flash",
                    "variant": "low",
                },
                "fixer": {
                    "model": "bf/huggingface/novita/deepseek-ai/DeepSeek-V4-Pro",
                    "variant": "high",
                },
                "designer": {"model": "bf-o/gpt-5.6-luna", "variant": "medium"},
                "observer": {"model": "bf/gemini/gemini-3-flash-preview"},
            }
        },
        "agents": {
            "navigator": {"model": "bf/gemini/gemini-3-flash-preview"},
            "detective": {
                "model": "bf/huggingface/fireworks-ai/deepseek-ai/DeepSeek-V4-Flash",
                "variant": "high",
            },
            "sage": {
                "model": "bf/huggingface/fireworks-ai/deepseek-ai/DeepSeek-V4-Flash",
            },
            "reviewer": {"model": "bf-o/gpt-5.6-luna", "variant": "medium"},
            "reviewer-code": {"model": "bf-o/gpt-5.6-luna", "variant": "medium"},
            "reviewer-comments": {"model": "bf-o/gpt-5.6-luna", "variant": "medium"},
            "reviewer-test": {"model": "bf-o/gpt-5.6-luna", "variant": "medium"},
            "reviewer-errors": {"model": "bf-o/gpt-5.6-luna", "variant": "medium"},
            "reviewer-types": {"model": "bf-o/gpt-5.6-luna", "variant": "medium"},
            "reviewer-security": {"model": "bf-o/gpt-5.6-luna", "variant": "medium"},
            "reviewer-performance": {
                "model": "bf-o/gpt-5.6-luna",
                "variant": "medium",
            },
            "reviewer-data-integrity": {
                "model": "bf-o/gpt-5.6-luna",
                "variant": "medium",
            },
            "reviewer-simplifier": {
                "model": "bf-o/gpt-5.6-luna",
                "variant": "medium",
            },
            "reviewer-accessibility": {
                "model": "bf-o/gpt-5.6-luna",
                "variant": "medium",
            },
        },
    }


def _make_profile(agents_dict):
    """Return a minimal profile dict with version 1 and given agent entries."""
    return {"version": PROFILE_SCHEMA_VERSION, "agents": agents_dict}


# ---------------------------------------------------------------------------
# Schema rejection tests
# ---------------------------------------------------------------------------

def test_schema_missing_version():
    profile = {"agents": {"orchestrator": {"model": "m1"}}}
    try:
        _validate_profile("fake.yml", profile)
        assert False, "expected ValueError for missing version"
    except ValueError as e:
        assert "version" in str(e).lower()


def test_schema_wrong_version():
    profile = {"version": 99, "agents": {"orchestrator": {"model": "m1"}}}
    try:
        _validate_profile("fake.yml", profile)
        assert False, "expected ValueError for wrong version"
    except ValueError as e:
        assert str(PROFILE_SCHEMA_VERSION) in str(e)


def test_schema_missing_agents():
    profile = {"version": PROFILE_SCHEMA_VERSION}
    try:
        _validate_profile("fake.yml", profile)
        assert False, "expected ValueError for missing agents"
    except ValueError as e:
        assert "agents" in str(e).lower()


def test_schema_agent_non_string_key():
    profile = {"version": PROFILE_SCHEMA_VERSION, "agents": {1: {"model": "m1"}}}
    try:
        _validate_profile("fake.yml", profile)
        assert False, "expected ValueError for non-string agent key"
    except ValueError as e:
        assert "non-empty string" in str(e).lower()


def test_schema_spec_not_mapping():
    profile = {
        "version": PROFILE_SCHEMA_VERSION,
        "agents": {"orchestrator": "not-a-map"},
    }
    try:
        _validate_profile("fake.yml", profile)
        assert False, "expected ValueError for non-mapping spec"
    except ValueError as e:
        assert "must be a mapping" in str(e).lower()


def test_schema_missing_model():
    profile = {
        "version": PROFILE_SCHEMA_VERSION,
        "agents": {"orchestrator": {"variant": "high"}},
    }
    try:
        _validate_profile("fake.yml", profile)
        assert False, "expected ValueError for missing model"
    except ValueError as e:
        assert "model" in str(e).lower()


def test_schema_empty_model():
    profile = {
        "version": PROFILE_SCHEMA_VERSION,
        "agents": {"orchestrator": {"model": ""}},
    }
    try:
        _validate_profile("fake.yml", profile)
        assert False, "expected ValueError for empty model"
    except ValueError as e:
        assert "non-empty string" in str(e).lower()


# ---------------------------------------------------------------------------
# Profile application tests
# ---------------------------------------------------------------------------

def test_apply_default_profile():
    """Default profile overwrites model and variant on matching agents."""
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / "src"
        profiles_dir = src / "profiles" / "models"
        profiles_dir.mkdir(parents=True, exist_ok=True)
        (profiles_dir / "default.yml").write_text(
            yaml.safe_dump(
                _make_profile(
                    {
                        "orchestrator": {
                            "model": "bf-o/NEW-MODEL",
                            "variant": "high",
                        },
                        "oracle": {"model": "bf-o/C-ORACLE", "variant": "high"},
                        "fixer": {
                            "model": "bf/huggingface/novita/deepseek-ai/DeepSeek-V4-Pro",
                            "variant": "high",
                        },
                        "detective": {
                            "model": "bf/huggingface/fireworks-ai/deepseek-ai/DeepSeek-V4-Flash",
                            "variant": "high",
                        },
                        "reviewer": {"model": "bf-o/REV-EW", "variant": "medium"},
                        "reviewer-code": {
                            "model": "bf-o/REV-COE",
                            "variant": "medium",
                        },
                        "reviewer-comments": {
                            "model": "bf-o/REV-CMT",
                            "variant": "medium",
                        },
                        "reviewer-test": {
                            "model": "bf-o/REV-TST",
                            "variant": "medium",
                        },
                        "reviewer-errors": {
                            "model": "bf-o/REV-ERR",
                            "variant": "medium",
                        },
                        "reviewer-types": {
                            "model": "bf-o/REV-TYP",
                            "variant": "medium",
                        },
                        "reviewer-security": {
                            "model": "bf-o/REV-SEC",
                            "variant": "medium",
                        },
                        "reviewer-performance": {
                            "model": "bf-o/REV-PRF",
                            "variant": "medium",
                        },
                        "reviewer-data-integrity": {
                            "model": "bf-o/REV-DAT",
                            "variant": "medium",
                        },
                        "reviewer-simplifier": {
                            "model": "bf-o/REV-SIM",
                            "variant": "medium",
                        },
                        "reviewer-accessibility": {
                            "model": "bf-o/REV-ACC",
                            "variant": "medium",
                        },
                        "navigator": {"model": "bf/gemini/NEW-NAV"},
                        "sage": {"model": "bf-huggingface/NEW-SAGE"},
                    }
                )
            )
        )

        omo = _make_omo()
        omo_path = src / "oh-my-opencode-slim.json"
        omo_path.write_text(json.dumps(omo, indent=2))

        _patch_config(str(src), "default")

        result = json.loads(omo_path.read_text())
        assert (
            result["presets"]["bifrost"]["orchestrator"]["model"]
            == "bf-o/NEW-MODEL"
        )
        # explorer NOT in profile -> untouched
        assert (
            result["presets"]["bifrost"]["explorer"]["model"]
            == "bf/huggingface/fireworks-ai/deepseek-ai/DeepSeek-V4-Flash"
        )
        assert result["agents"]["navigator"]["model"] == "bf/gemini/NEW-NAV"
        assert result["agents"]["reviewer"]["variant"] == "medium"


def test_apply_cost_efficient_profile():
    """Cost-efficient profile overwrites model and variant on matching agents."""
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / "src"
        profiles_dir = src / "profiles" / "models"
        profiles_dir.mkdir(parents=True, exist_ok=True)
        (profiles_dir / "cost-efficient.yml").write_text(
            yaml.safe_dump(
                _make_profile(
                    {
                        "orchestrator": {
                            "model": "bf/gemini/CE-ORCH",
                            "variant": "high",
                        },
                        "fixer": {
                            "model": "bf/huggingface/novita/CE-FIXER",
                            "variant": "high",
                        },
                        "reviewer-code": {
                            "model": "bf/huggingface/CE-RCODE",
                            "variant": "medium",
                        },
                    }
                )
            )
        )

        omo = _make_omo()
        omo_path = src / "oh-my-opencode-slim.json"
        omo_path.write_text(json.dumps(omo, indent=2))

        _patch_config(str(src), "cost-efficient")

        result = json.loads(omo_path.read_text())
        assert (
            result["presets"]["bifrost"]["orchestrator"]["model"]
            == "bf/gemini/CE-ORCH"
        )
        assert (
            result["agents"]["reviewer-code"]["model"]
            == "bf/huggingface/CE-RCODE"
        )
        # oracle NOT in profile -> untouched
        assert (
            result["presets"]["bifrost"]["oracle"]["model"]
            == "bf-o/gpt-5.6-luna"
        )


def test_missing_agent_in_profile_ignored():
    """Agents missing from the profile should not be changed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / "src"
        profiles_dir = src / "profiles" / "models"
        profiles_dir.mkdir(parents=True, exist_ok=True)
        (profiles_dir / "default.yml").write_text(
            yaml.safe_dump(
                _make_profile(
                    {
                        "orchestrator": {
                            "model": "bf-o/NEW-MODEL",
                            "variant": "high",
                        },
                    }
                )
            )
        )

        omo = _make_omo()
        omo_path = src / "oh-my-opencode-slim.json"
        omo_path.write_text(json.dumps(omo, indent=2))

        _patch_config(str(src), "default")

        result = json.loads(omo_path.read_text())
        # oracle not in profile -> untouched
        assert (
            result["presets"]["bifrost"]["oracle"]["model"]
            == "bf-o/gpt-5.6-luna"
        )
        assert result["presets"]["bifrost"]["oracle"]["variant"] == "high"


def test_variant_preservation():
    """Profile must set variant only when declared, otherwise leave existing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / "src"
        profiles_dir = src / "profiles" / "models"
        profiles_dir.mkdir(parents=True, exist_ok=True)
        profile_data = _make_profile(
            {
                "reviewer": {"model": "bf-o/NEWREV", "variant": "high"},
                "reviewer-code": {"model": "bf-o/NEWCODE", "variant": "low"},
                "sage": {"model": "bf-huggingface/NEWSAGE"},
            }
        )
        (profiles_dir / "default.yml").write_text(yaml.safe_dump(profile_data))

        omo = _make_omo()
        omo["agents"]["sage"]["variant"] = "existing"
        omo_path = src / "oh-my-opencode-slim.json"
        omo_path.write_text(json.dumps(omo, indent=2))

        _patch_config(str(src), "default")

        result = json.loads(omo_path.read_text())
        assert result["agents"]["reviewer"]["variant"] == "high"
        assert result["agents"]["reviewer-code"]["variant"] == "low"
        # sage variant untouched because profile doesn't declare one
        assert result["agents"]["sage"]["variant"] == "existing"


# ---------------------------------------------------------------------------
# Invalid variant rejection
# ---------------------------------------------------------------------------

def test_schema_null_variant_rejected():
    """variant: null (present key, None value) is rejected."""
    profile = {
        "version": PROFILE_SCHEMA_VERSION,
        "agents": {"orchestrator": {"model": "m1", "variant": None}},
    }
    try:
        _validate_profile("fake.yml", profile)
        assert False, "expected ValueError for null variant"
    except ValueError as e:
        assert "variant" in str(e).lower()


def test_schema_empty_variant_rejected():
    """variant: '' (empty string) is rejected."""
    profile = {
        "version": PROFILE_SCHEMA_VERSION,
        "agents": {"orchestrator": {"model": "m1", "variant": ""}},
    }
    try:
        _validate_profile("fake.yml", profile)
        assert False, "expected ValueError for empty variant"
    except ValueError as e:
        assert "non-empty string" in str(e).lower()


def test_schema_non_string_variant_rejected():
    """variant: 123 (integer) is rejected."""
    profile = {
        "version": PROFILE_SCHEMA_VERSION,
        "agents": {"orchestrator": {"model": "m1", "variant": 123}},
    }
    try:
        _validate_profile("fake.yml", profile)
        assert False, "expected ValueError for non-string variant"
    except ValueError as e:
        assert "variant" in str(e).lower()


# ---------------------------------------------------------------------------
# Missing-agent / duplicate-agent error
# ---------------------------------------------------------------------------

def test_missing_profile_agent_raises():
    """A profile agent not found in active preset or custom agents fails."""
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / "src"
        profiles_dir = src / "profiles" / "models"
        profiles_dir.mkdir(parents=True, exist_ok=True)
        (profiles_dir / "default.yml").write_text(
            yaml.safe_dump(
                _make_profile(
                    {
                        "orchestrator": {
                            "model": "bf-o/gpt-5.6-luna",
                            "variant": "high",
                        },
                        "nonexistent": {"model": "bf/does-not-exist"},
                    }
                )
            )
        )
        omo = _make_omo()
        omo_path = src / "oh-my-opencode-slim.json"
        omo_path.write_text(json.dumps(omo, indent=2))

        try:
            _patch_config(str(src), "default")
            assert False, "expected ValueError for missing profile agent"
        except ValueError as e:
            assert "nonexistent" in str(e)


def test_duplicate_agent_preset_and_custom_raises():
    """An agent present in both preset and custom agents fails."""
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / "src"
        profiles_dir = src / "profiles" / "models"
        profiles_dir.mkdir(parents=True, exist_ok=True)
        (profiles_dir / "default.yml").write_text(
            yaml.safe_dump(
                _make_profile(
                    {
                        "orchestrator": {
                            "model": "bf-o/gpt-5.6-luna",
                            "variant": "high",
                        },
                    }
                )
            )
        )
        omo = _make_omo()
        # Duplicate orchestrator into custom agents as well
        omo["agents"]["orchestrator"] = {
            "model": "bf-o/gpt-5.6-luna",
            "variant": "high",
        }
        omo_path = src / "oh-my-opencode-slim.json"
        omo_path.write_text(json.dumps(omo, indent=2))

        try:
            _patch_config(str(src), "default")
            assert False, "expected ValueError for duplicate agent"
        except ValueError as e:
            assert "both" in str(e).lower() or "duplicate" in str(e).lower()


# ---------------------------------------------------------------------------
# Active-preset resolution (not hard-coded bifrost)
# ---------------------------------------------------------------------------

def test_active_preset_resolution():
    """Application uses config.preset, not hard-coded 'bifrost'."""
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / "src"
        profiles_dir = src / "profiles" / "models"
        profiles_dir.mkdir(parents=True, exist_ok=True)
        (profiles_dir / "default.yml").write_text(
            yaml.safe_dump(
                _make_profile(
                    {
                        "orchestrator": {
                            "model": "bf-o/PRESET-RESOLVED",
                            "variant": "high",
                        },
                        "navigator": {"model": "bf/gemini/PRESET-NEW-NAV"},
                    }
                )
            )
        )

        omo = _make_omo()
        # Switch active preset to 'custom-preset' with its own agents
        omo["preset"] = "custom-preset"
        omo["presets"]["custom-preset"] = {
            "orchestrator": {"model": "bf-o/gpt-5.6-luna", "variant": "high"},
            "oracle": {"model": "bf-o/gpt-5.6-luna", "variant": "high"},
        }
        # navigator lives in custom agents (not in active preset)
        omo_path = src / "oh-my-opencode-slim.json"
        omo_path.write_text(json.dumps(omo, indent=2))

        _patch_config(str(src), "default")

        result = json.loads(omo_path.read_text())
        # orchestrator resolved in active preset 'custom-preset'
        assert (
            result["presets"]["custom-preset"]["orchestrator"]["model"]
            == "bf-o/PRESET-RESOLVED"
        )
        # navigator resolved in custom agents (not in active preset)
        assert result["agents"]["navigator"]["model"] == "bf/gemini/PRESET-NEW-NAV"
        # bifrost preset untouched (not the active preset)
        assert (
            result["presets"]["bifrost"]["orchestrator"]["model"]
            == "bf-o/gpt-5.6-luna"
        )


# ---------------------------------------------------------------------------
# Omitted variant leaves target unchanged
# ---------------------------------------------------------------------------

def test_omitted_variant_preserves_existing():
    """When profile omits variant, the agent's existing variant is untouched."""
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / "src"
        profiles_dir = src / "profiles" / "models"
        profiles_dir.mkdir(parents=True, exist_ok=True)
        (profiles_dir / "default.yml").write_text(
            yaml.safe_dump(
                _make_profile(
                    {
                        "oracle": {
                            "model": "bf-o/ORACLE-NEW",
                            # variant intentionally absent
                        },
                    }
                )
            )
        )
        omo = _make_omo()
        omo["presets"]["bifrost"]["oracle"]["variant"] = "preexisting-high"
        omo_path = src / "oh-my-opencode-slim.json"
        omo_path.write_text(json.dumps(omo, indent=2))

        _patch_config(str(src), "default")

        result = json.loads(omo_path.read_text())
        assert result["presets"]["bifrost"]["oracle"]["model"] == "bf-o/ORACLE-NEW"
        # variant untouched
        assert result["presets"]["bifrost"]["oracle"]["variant"] == "preexisting-high"


# ---------------------------------------------------------------------------
# Fixer regression guard (real source files)
# ---------------------------------------------------------------------------

FIXER_MODEL = "bf/huggingface/novita/deepseek-ai/DeepSeek-V4-Pro"


def test_fixer_unchanged_in_profiles_and_omo():
    """Fixer stays Novita DeepSeek V4 Pro high in both profiles and the OMO config."""
    repo_root = _HERE.parent
    for profile_name in ("default", "cost-efficient"):
        profile_path = repo_root / "profiles" / "models" / f"{profile_name}.yml"
        with open(profile_path, "r") as f:
            profile = yaml.safe_load(f)
        fixer = profile["agents"]["fixer"]
        assert fixer["model"] == FIXER_MODEL, (
            f"profile {profile_name!r} fixer model drifted: {fixer['model']!r}"
        )
        assert fixer["variant"] == "high", (
            f"profile {profile_name!r} fixer variant drifted: {fixer['variant']!r}"
        )

    omo_path = repo_root / "oh-my-opencode-slim.json"
    with open(omo_path, "r") as f:
        omo = json.load(f)
    fixer = omo["presets"]["bifrost"]["fixer"]
    assert fixer["model"] == FIXER_MODEL, f"OMO fixer model drifted: {fixer['model']!r}"
    assert fixer["variant"] == "high", f"OMO fixer variant drifted: {fixer['variant']!r}"
    assert fixer.get("skills") == ["fixer"], f"OMO fixer skills drifted: {fixer.get('skills')!r}"
    assert fixer.get("mcps") == ["codebase-memory-mcp"], (
        f"OMO fixer mcps drifted: {fixer.get('mcps')!r}"
    )


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def run_all():
    tests = [
        fn
        for name, fn in sorted(globals().items())
        if name.startswith("test_") and callable(fn)
    ]
    passed = 0
    failed = 0
    for fn in tests:
        try:
            fn()
            passed += 1
        except Exception as e:
            print(f"FAIL {fn.__name__}: {e}", file=sys.stderr)
            failed += 1
    print(f"\nResults: {passed} passed, {failed} failed")
    return failed


if __name__ == "__main__":
    sys.exit(run_all())