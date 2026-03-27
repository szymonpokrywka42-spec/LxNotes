import json
from pathlib import Path
import unittest


class TestLanguageKeysConsistency(unittest.TestCase):
    def test_all_languages_include_en_us_keys(self):
        lang_dir = Path("assets/languages")
        base_path = lang_dir / "en-us.json"
        self.assertTrue(base_path.exists(), "Missing base language file en-us.json")

        with base_path.open("r", encoding="utf-8") as f:
            base_keys = set(json.load(f).keys())

        for path in sorted(lang_dir.glob("*.json")):
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            keys = set(data.keys())
            missing = sorted(base_keys - keys)
            self.assertFalse(
                missing,
                f"{path.name} is missing {len(missing)} keys (e.g. {missing[:5]})",
            )

    def test_runtime_product_terms_are_consistent(self):
        lang_dir = Path("assets/languages")
        checks = {
            "file_goto_unavailable_large_view": ["GoToLine", "Large Viewer"],
            "file_goto_engine_unavailable": ["GoToLine"],
            "file_large_viewer_restored_enabled": ["Large Viewer"],
            "file_large_viewer_ultra_enabled": ["Large Viewer"],
            "file_turbo_enabled": ["Turbo"],
            "console_cmd_turbo_enabled": ["Turbo"],
            "console_cmd_turbo_disabled": ["Turbo"],
            "console_cmd_turbo_auto": ["Turbo"],
        }

        for path in sorted(lang_dir.glob("*.json")):
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            for key, required_tokens in checks.items():
                value = str(data.get(key, ""))
                for token in required_tokens:
                    self.assertIn(
                        token,
                        value,
                        f"{path.name} key '{key}' should contain token '{token}'",
                    )


if __name__ == "__main__":
    unittest.main()
