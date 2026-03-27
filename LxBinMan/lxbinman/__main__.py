from __future__ import annotations

import argparse
import json

from . import builder, feedback


def main() -> int:
    parser = argparse.ArgumentParser(prog="lxbinman")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_h = sub.add_parser("healthcheck")
    p_h.add_argument("--source-dir", required=True)
    p_h.add_argument("--json", action="store_true")

    p_b = sub.add_parser("build")
    p_b.add_argument("--source-dir", required=True)
    p_b.add_argument(
        "--policy",
        default="prefer_prebuilt",
        choices=["prefer_prebuilt", "prefer_cache", "build_only", "prebuilt_only"],
    )
    p_b.add_argument("--json", action="store_true")

    p_fb = sub.add_parser("fast-build")
    p_fb.add_argument("--source-dir", required=True)
    p_fb.add_argument("--output-dir")
    p_fb.add_argument("--json", action="store_true")

    p_t = sub.add_parser("toolchain")
    p_t.add_argument("--source-dir", required=True)
    p_t.add_argument("--compiler", default="g++")
    p_t.add_argument("--json", action="store_true")

    p_c = sub.add_parser("clean")
    p_c.add_argument("--source-dir", required=True)
    p_c.add_argument("--profile", choices=["dev", "ci", "release"])
    p_c.add_argument("--mode", choices=["light", "standard", "deep"], default="standard")
    p_c.add_argument("--no-cache", action="store_true")
    p_c.add_argument("--no-local-outputs", action="store_true")
    p_c.add_argument("--no-orphans", action="store_true")
    p_c.add_argument("--pycache", action="store_true")
    p_c.add_argument("--build-artifacts", action="store_true")
    p_c.add_argument("--exclude", action="append", default=[])
    p_c.add_argument("--dry-run", action="store_true")
    p_c.add_argument("--json", action="store_true")

    p_p = sub.add_parser("prune")
    p_p.add_argument("--source-dir", required=True)
    p_p.add_argument("--max-versions", type=int, default=3)
    p_p.add_argument("--max-age-days", type=int, default=30)
    p_p.add_argument("--dry-run", action="store_true")
    p_p.add_argument("--json", action="store_true")

    args = parser.parse_args()
    json_mode = bool(getattr(args, "json", False))
    feedback.enable_console(not json_mode)

    if args.cmd == "healthcheck":
        out = builder.healthcheck(source_dir=args.source_dir)
        print(json.dumps(out, indent=2 if json_mode else 2, ensure_ascii=False))
        return 0

    if args.cmd == "build":
        report = builder.build_all(source_dir=args.source_dir, policy=args.policy, return_report=True)
        ok = report.get("ok", {})
        failed = report.get("failed", [])
        if json_mode:
            payload = {
                "engines_ok": len(ok),
                "engines_failed": len(failed),
                "failed": failed,
                "ok": sorted(ok.keys()) if isinstance(ok, dict) else [],
            }
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(f"engines_ok={len(ok)}")
        if failed:
            if not json_mode:
                print(f"engines_failed={len(failed)}")
            return 2
        return 0

    if args.cmd == "fast-build":
        out = builder.fast_boot_build_all(
            source_dir=args.source_dir,
            output_dir=args.output_dir,
        )
        if json_mode:
            print(json.dumps({"engines": len(out), "names": sorted(out.keys())}, ensure_ascii=False))
        else:
            print(f"engines={len(out)}")
        return 0

    if args.cmd == "toolchain":
        out = builder.snapshot_toolchain(
            source_dir=args.source_dir,
            compiler=args.compiler,
            persist=True,
        )
        print(json.dumps(out, indent=2 if json_mode else 2, ensure_ascii=False))
        return 0

    if args.cmd == "clean":
        out = builder.clean_binaries(
            source_dir=args.source_dir,
            profile=args.profile,
            mode=args.mode,
            remove_cache=False if args.no_cache else None,
            remove_local_outputs=not args.no_local_outputs,
            remove_orphans=not args.no_orphans,
            remove_pycache=True if args.pycache else None,
            remove_build_artifacts=True if args.build_artifacts else None,
            exclude=args.exclude,
            dry_run=args.dry_run,
        )
        print(json.dumps(out, indent=2 if json_mode else 2, ensure_ascii=False))
        return 0

    if args.cmd == "prune":
        out = builder.prune_cache(
            source_dir=args.source_dir,
            max_versions=args.max_versions,
            max_age_days=args.max_age_days,
            dry_run=args.dry_run,
        )
        print(json.dumps(out, indent=2 if json_mode else 2, ensure_ascii=False))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
