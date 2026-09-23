import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_VALIDATOR_SPEC = importlib.util.spec_from_file_location(
    "validate_pi_config", ROOT / "scripts" / "validate-pi-config.py"
)
assert _VALIDATOR_SPEC and _VALIDATOR_SPEC.loader
_VALIDATOR_MODULE = importlib.util.module_from_spec(_VALIDATOR_SPEC)
_VALIDATOR_SPEC.loader.exec_module(_VALIDATOR_MODULE)
validate_payloads = _VALIDATOR_MODULE.validate_payloads


def load_payloads():
    return [
        json.loads((ROOT / "pi-config" / name).read_text(encoding="utf-8"))
        for name in ("models.json", "settings.json", "mcp.json")
    ]


class PiConfigValidationTests(unittest.TestCase):
    def assert_rejected(self, mutate):
        models, settings, mcp = load_payloads()
        mutate(models, settings, mcp)
        errors = validate_payloads(models, settings, mcp)
        self.assertTrue(errors, "mutated payload should be rejected")

    def test_valid_payloads(self):
        self.assertEqual(validate_payloads(*load_payloads()), [])

    def test_rejects_literal_secret(self):
        self.assert_rejected(
            lambda models, settings, mcp: models["providers"]["bifrost"].update(
                apiKey="sk-live-123456789"
            )
        )

    def test_rejects_unapproved_package(self):
        self.assert_rejected(
            lambda models, settings, mcp: settings["packages"].append("npm:unapproved")
        )

    def test_rejects_missing_model_field(self):
        def remove_field(models, settings, mcp):
            del models["providers"]["bifrost"]["models"][0]["contextWindow"]

        self.assert_rejected(remove_field)

    def test_rejects_non_bifrost_endpoint(self):
        self.assert_rejected(
            lambda models, settings, mcp: models["providers"]["bifrost"].update(
                baseUrl="https://example.invalid/v1"
            )
        )

    def test_rejects_non_luna_default(self):
        self.assert_rejected(lambda models, settings, mcp: settings.update(defaultModel="gpt-5.5"))

    def test_rejects_unsafe_mcp_defaults(self):
        self.assert_rejected(lambda models, settings, mcp: mcp.update(directTools=True))

    def test_rejects_unapproved_mcp_server(self):
        self.assert_rejected(
            lambda models, settings, mcp: mcp["mcpServers"].update(example={"command": ["unsafe"]})
        )

    def test_rejects_missing_mcp_install_guard(self):
        def remove_guard(models, settings, mcp):
            del mcp["allowInstall"]

        self.assert_rejected(remove_guard)

    def test_rejects_extra_model(self):
        def add_model(models, settings, mcp):
            models["providers"]["bifrost"]["models"].append(
                copy.deepcopy(models["providers"]["bifrost"]["models"][0])
            )

        self.assert_rejected(add_model)


if __name__ == "__main__":
    unittest.main()
