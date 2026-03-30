#!/usr/bin/env python3
"""
Sanity-check Java vs Apple Silicon for bundled unidbg JNA (x86_64-only darwin dispatch).
Run from project root: python scripts/verify_environment.py
Exit 0 if OK or not applicable; exit 1 if arm64 JVM on Apple Silicon (will break unidbg).
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys


def jvm_os_arch(java_exe: str) -> str | None:
    try:
        p = subprocess.run(
            [java_exe, "-XshowSettings:properties", "-version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        text = (p.stderr or "") + "\n" + (p.stdout or "")
        for raw in text.splitlines():
            line = raw.strip()
            if line.startswith("os.arch") and "=" in line:
                return line.split("=", 1)[1].strip()
    except (OSError, subprocess.TimeoutExpired):
        return None
    return None


def main() -> int:
    print(f"platform: {platform.system()} {platform.machine()}")
    java = shutil.which("java")
    if not java:
        print("ERROR: no `java` on PATH")
        return 1
    print(f"java: {java}")
    arch = jvm_os_arch(java)
    print(f"jvm os.arch: {arch!r}")

    if platform.system() != "Darwin" or platform.machine() != "arm64":
        print("OK: Apple Silicon + arm64 JVM check not required on this machine.")
        return 0

    if arch in ("x86_64", "amd64", "i386"):
        print("OK: JVM is x86_64 — matches bundled JNA darwin dispatch.")
        return 0

    if arch in ("aarch64", "arm64"):
        print(
            "FAIL: arm64 JVM cannot load x86_64-only JNA inside unidbg.jar "
            "(UnsatisfiedLinkError on jna*.tmp).\n"
            "Install an Intel (x64) JDK and set JAVA_HOME, then re-run; "
            "os.arch should become x86_64."
        )
        return 1

    print("WARN: unknown os.arch — unidbg may still fail.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
