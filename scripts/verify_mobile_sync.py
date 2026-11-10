#!/usr/bin/env python3
"""
SCOS Mobile Assets Sync & Parity Verification Script

Ensures that frontend changes in backend/static/ are not left stale
in the Android Capacitor asset directory mobile/android/app/src/main/assets/public/.

Usage:
    python scripts/verify_mobile_sync.py [--fix]
"""
import os
import sys
import filecmp
import subprocess

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BACKEND_STATIC = os.path.join(REPO_ROOT, "backend", "static")
MOBILE_PUBLIC = os.path.join(REPO_ROOT, "mobile", "android", "app", "src", "main", "assets", "public")

IGNORED_EXTS = ('.bak', '.tmp', '.DS_Store', 'Thumbs.db')


def audit_sync():
    discrepancies = []
    total_checked = 0

    if not os.path.exists(MOBILE_PUBLIC):
        return [f"Mobile public assets directory does not exist: {MOBILE_PUBLIC}"]

    for root, dirs, files in os.walk(BACKEND_STATIC):
        dirs[:] = [d for d in dirs if d not in ('.git', '__pycache__', 'node_modules')]
        rel_dir = os.path.relpath(root, BACKEND_STATIC)
        for f in files:
            if any(f.endswith(ext) for ext in IGNORED_EXTS):
                continue
            src_file = os.path.join(root, f)
            dest_file = os.path.join(MOBILE_PUBLIC, rel_dir, f)
            total_checked += 1

            if not os.path.exists(dest_file):
                discrepancies.append(f"MISSING IN MOBILE: {os.path.join(rel_dir, f)}")
            elif not filecmp.cmp(src_file, dest_file, shallow=False):
                discrepancies.append(f"CONTENT DIVERGENCE: {os.path.join(rel_dir, f)}")

    return discrepancies, total_checked


def main():
    auto_fix = "--fix" in sys.argv

    print("[SCOS Mobile Sync] Auditing frontend assets between Web and Android Mobile...")
    discrepancies, count = audit_sync()

    if discrepancies:
        print(f"[FAIL] Found {len(discrepancies)} stale or missing asset(s) across {count} files:")
        for d in discrepancies[:20]:
            print(f"  - {d}")

        if auto_fix:
            print("\n[INFO] Running 'npx cap copy' in mobile directory...")
            try:
                subprocess.check_call(["npx", "cap", "copy"], cwd=os.path.join(REPO_ROOT, "mobile"), shell=True)
                print("[PASS] Synchronization complete. Re-verifying...")
                remaining, _ = audit_sync()
                if not remaining:
                    print("[PASS] All assets verified 100% in sync.")
                    return 0
                else:
                    print(f"[FAIL] {len(remaining)} discrepancies remain after copy.")
                    return 1
            except Exception as e:
                print(f"[ERROR] Failed to execute 'npx cap copy': {e}")
                return 1
        else:
            print("\n[HINT] Run with --fix or execute 'cd mobile; npx cap copy' to synchronize.")
            return 1

    print(f"[PASS] All {count} frontend assets are 100% synchronized between Web and Android Mobile.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
