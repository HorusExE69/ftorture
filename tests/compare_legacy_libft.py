"""Compare full libft behavior against a Git revision of the Bash runner.

This is an explicit integration check, not part of unittest discovery. Student
projects are copied before any make command; only temporary copies are built.
"""
import argparse
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent.parent


def compare(project: Path, legacy_ref: str, temporary: Path) -> bool:
    commit = subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "--verify", f"{legacy_ref}^{{commit}}"], text=True).strip()
    archive = subprocess.check_output(["git", "-C", str(ROOT), "archive", "--format=zip", commit])
    legacy = temporary / "legacy"
    legacy.mkdir()
    with zipfile.ZipFile(io.BytesIO(archive)) as files:
        files.extractall(legacy)
    if not (legacy / "torture.sh").is_file() or (legacy / "ftorture").exists():
        raise ValueError("legacy revision must contain the original Bash runner, not a Python compatibility launcher")
    results = {}
    for name, command, report in (
        ("shell", ["bash", str(legacy / "torture.sh")], legacy / "ftorture.log"),
        ("python", [sys.executable, str(ROOT / "torture.py")], ROOT / "ftorture.log"),
    ):
        student = temporary / f"{name}-libft"
        shutil.copytree(project, student, ignore=shutil.ignore_patterns(".git"))
        args = [*command, "libft", str(student), "--no-checks", "--seed", "42", "--no-color"]
        if name == "python":
            args += ["--lang", "fr", "--custom-tests-dir", str(temporary / "no-custom-tests")]
        run = subprocess.run(args, capture_output=True, text=True, timeout=180,
                             env={**os.environ, "LC_ALL": "C", "FTORTURE_LANG": "fr"})
        (temporary / f"{name}-output.txt").write_text(run.stdout + run.stderr)
        if not report.is_file():
            raise ValueError(f"{name} produced no report (status {run.returncode}):\n{run.stdout[-2000:]}{run.stderr}")
        lines = report.read_text().splitlines()
        totals = [line for line in lines if line.startswith("TOTAL:")]
        functions = [line for line in lines if re.fullmatch(r".+ : \d+/\d+ \(\d+ spéculatif\)", line)]
        if not totals or len(functions) != 43:
            raise ValueError(f"{name} did not report all 43 libft functions (status {run.returncode})")
        results[name] = {"status": run.returncode, "totals": totals, "functions": functions}
    print(json.dumps({name: {"status": result["status"], "totals": result["totals"],
                            "functions_compared": len(result["functions"])}
                      for name, result in results.items()}, indent=2, ensure_ascii=False))
    equal = results["shell"] == results["python"]
    print("Full libft behavioral parity confirmed." if equal else "Legacy/Python behavioral results differ.")
    print("The original student directory was not modified.")
    if not equal:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    return equal


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path, help="libft directory to copy and test")
    parser.add_argument("--legacy-ref", default="9d3adcc", help="Git revision with the original Bash runner")
    args = parser.parse_args()
    project = args.project.expanduser().resolve()
    if not (project / "libft.h").is_file() or not (project / "Makefile").is_file():
        parser.error("expected a libft directory with libft.h and Makefile")
    preferred = Path("/tmp/opencode")
    try:
        with tempfile.TemporaryDirectory(prefix="ftorture-parity-", dir=preferred if preferred.is_dir() else None) as tmp:
            return 0 if compare(project, args.legacy_ref, Path(tmp)) else 1
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"parity: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
