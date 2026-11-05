#!/usr/bin/env python3
"""Reject skipped project patches and verify CPU code in the linked kernel."""
from pathlib import Path
import argparse
import shlex
import subprocess


SKIP = 'warning "Skipping patch ${PATCH} (already upstream, previously applied, or malformed): ${APPLY_CHECK}"'
CPU_MARKERS = (
    b"SWEET CPU: before ml_processor_register",
    b"SWEET CPU: after ml_processor_register",
    b"SWEET CPU: before processor_start",
    b"SWEET CPU: after processor_start",
    b"SWEET CPU: before ml_set_max_cpus",
    b"SWEET CPU: after ml_set_max_cpus",
)


def guard_patches(build_script: Path, patch_dir: Path) -> None:
    patches = sorted(patch_dir.resolve().glob("*.patch"))
    if not patches:
        raise SystemExit("No project patches found")
    for patch in patches:
        result = subprocess.run(
            ["git", "apply", "--stat", "--", str(patch)],
            capture_output=True, text=True,
        )
        if result.returncode:
            raise SystemExit(f"Malformed project patch {patch.name}:\n{result.stderr}")
    source = build_script.read_text(encoding="utf-8")
    if source.count(SKIP) != 1:
        raise SystemExit("Pinned build script changed: patch-skip guard not found exactly once")
    project_dir = shlex.quote(str(patch_dir.resolve()))
    guard = (
        f'if [ -f {project_dir}/"$(basename "$PATCH")" ]; then\n'
        '                    printf "Project patch cannot be skipped: %s\\n%s\\n" "$PATCH" "$APPLY_CHECK" >&2\n'
        '                    exit 1\n'
        '                fi\n'
        '                ' + SKIP
    )
    with build_script.open("w", encoding="utf-8", newline="\n") as output:
        output.write(source.replace(SKIP, guard))
    print(f"Parsed {len(patches)} project patches; project patch skips now fail the build")


def verify_kernel(kernel: Path) -> None:
    data = kernel.read_bytes()
    missing = [marker.decode() for marker in CPU_MARKERS if marker not in data]
    if missing:
        raise SystemExit(f"Linked kernel {kernel} lacks CPU diagnostics: {', '.join(missing)}")
    print(f"Linked CPU diagnostics verified in {kernel}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    guard = commands.add_parser("guard-patches")
    guard.add_argument("build_script", type=Path)
    guard.add_argument("patch_dir", type=Path)
    verify = commands.add_parser("verify-kernel")
    verify.add_argument("kernel", type=Path)
    args = parser.parse_args()
    if args.command == "guard-patches":
        guard_patches(args.build_script, args.patch_dir)
    else:
        verify_kernel(args.kernel)
