import sys
import unittest
from pathlib import Path
from unittest.mock import patch
import warnings
import io
import contextlib
import json


ROOT = Path(__file__).resolve().parents[1]
LXBINMAN_ROOT = ROOT / "LxBinMan"
if str(LXBINMAN_ROOT) not in sys.path:
    sys.path.insert(0, str(LXBINMAN_ROOT))


class TestLxBinManSmoke(unittest.TestCase):
    def test_import_lxbinman_module(self):
        import lxbinman  # noqa: F401

        self.assertTrue(hasattr(lxbinman, "load"))
        self.assertTrue(hasattr(lxbinman, "feedback"))

    def test_invalid_policy_raises(self):
        import lxbinman.autobin as autobin

        with self.assertRaises(autobin.AutoBinError):
            autobin.load(
                "cpu",
                source_dir="/tmp/does-not-matter",
                policy="nope",  # type: ignore[arg-type]
            )

    def test_run_script_all_blocks_path_escape(self):
        import lxbinman.builder as builder

        with self.assertRaises(builder.BuilderError):
            builder.run_script_all(source_dir=ROOT, names=["../outside.py"])

    def test_cli_build_returns_nonzero_on_failures(self):
        import lxbinman.__main__ as cli

        with patch.object(
            cli.builder,
            "build_all",
            return_value={"ok": {"a": object()}, "failed": ["b"]},
        ):
            with patch.object(sys, "argv", ["lxbinman", "build", "--source-dir", "."]):
                rc = cli.main()
        self.assertEqual(rc, 2)

    def test_cli_build_json_output(self):
        import lxbinman.__main__ as cli

        with patch.object(
            cli.builder,
            "build_all",
            return_value={"ok": {"a": object(), "b": object()}, "failed": ["c"]},
        ):
            with patch.object(
                sys, "argv", ["lxbinman", "build", "--source-dir", ".", "--json"]
            ):
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    rc = cli.main()
        self.assertEqual(rc, 2)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["engines_ok"], 2)
        self.assertEqual(payload["engines_failed"], 1)
        self.assertEqual(payload["failed"], ["c"])

    def test_cli_healthcheck_json_output(self):
        import lxbinman.__main__ as cli

        with patch.object(
            cli.builder,
            "healthcheck",
            return_value={"runtime": {"python_version": "3.12"}, "checks": {"compiler": {"ok": True}}},
        ):
            with patch.object(
                sys, "argv", ["lxbinman", "healthcheck", "--source-dir", ".", "--json"]
            ):
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    rc = cli.main()
        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertTrue(payload["checks"]["compiler"]["ok"])

    def test_compat_layers_are_importable(self):
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("ignore", DeprecationWarning)
            import moduleapi  # noqa: F401
            import binman  # noqa: F401

    def test_moduleapi_feedback_alias_points_to_singleton(self):
        with warnings.catch_warnings(record=True):
            warnings.simplefilter("ignore", DeprecationWarning)
            from lxbinman import feedback as root_feedback
            from moduleapi.feedback import feedback as compat_feedback

        self.assertIs(root_feedback, compat_feedback)


if __name__ == "__main__":
    unittest.main()
