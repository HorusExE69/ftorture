"""Example user test: inspect a project without changing its files."""
from pathlib import Path
import sys

path = Path(sys.argv[1]) / "README.md"
if not path.is_file():
    print(f"Missing {path}")
    raise SystemExit(1)
print(f"Found {path}")
