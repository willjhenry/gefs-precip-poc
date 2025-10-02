#!/usr/bin/env python3
"""
Test runner for predict_live.py.

Finds the latest meta_*.json in MODEL_ARTIFACTS_DIR, extracts its tag, and
invokes predict_live.py with that tag. Uses --test-mode by default to keep the
run light.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

from hydro.common import (
    MODEL_ARTIFACTS_DIR,
    SCRIPTS_DIR,
    find_latest_meta_under_tag_dirs,
    tag_from_meta_path,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run predict_live with latest meta."
    )
    parser.add_argument(
        "--no-test-mode", action="store_true", help="Disable --test-mode flag"
    )
    parser.add_argument(
        "--extra-args", type=str, default="", help="Additional args to pass"
    )
    args = parser.parse_args()

    meta_path = find_latest_meta_under_tag_dirs(MODEL_ARTIFACTS_DIR)
    if not meta_path:
        print("No meta_*.json found in MODEL_ARTIFACTS_DIR", file=sys.stderr)
        sys.exit(1)

    tag = tag_from_meta_path(meta_path)
    if not tag:
        print(f"Could not extract tag from {meta_path}", file=sys.stderr)
        sys.exit(1)

    predict_script = os.path.join(SCRIPTS_DIR, "predict_live.py")
    if not os.path.exists(predict_script):
        print(
            f"predict_live.py not found at {predict_script}", file=sys.stderr
        )
        sys.exit(1)

    cmd = [sys.executable, predict_script, "--tag", tag]
    if not args.no_test_mode:
        cmd.append("--test-mode")
    if args.extra_args:
        cmd.extend(args.extra_args.split())

    print("Running:", " ".join(cmd))
    rc = subprocess.call(cmd)
    sys.exit(rc)


if __name__ == "__main__":
    main()
