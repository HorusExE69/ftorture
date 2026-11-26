#!/usr/bin/env python3
"""Install a direct ~/.local/bin launcher; optionally update from upstream."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import re

if sys.version_info < (3, 10):
    raise SystemExit("ftorture requires Python 3.10 or newer")

UPSTREAM = "https://github.com/HorusExE69/ftorture.git"
MARKER = "# ftorture managed launcher"
PATH_MARKER = "# ftorture: ~/.local/bin on PATH"


def detect_shell() -> str:
    """Prefer the running ancestor shell over the configured login shell."""
    pid = os.getppid()
    for _ in range(32):
        try:
            process = Path(f"/proc/{pid}")
            name = (process / "comm").read_text().strip().lstrip("-")
            if name in {"bash", "zsh", "fish", "sh", "dash", "ksh"}:
                return name
            status = (process / "status").read_text()
            parent = re.search(r"^PPid:\s*(\d+)", status, re.M)
            if parent is None or int(parent[1]) <= 1:
                break
            pid = int(parent[1])
        except OSError:
            break
    return Path(os.environ.get("SHELL", "")).name


def shell_configuration(home: Path, shell: str) -> tuple[Path, str] | None:
    if shell == "zsh":
        return Path(os.environ.get("ZDOTDIR") or home) / ".zshrc", 'export PATH="$HOME/.local/bin:$PATH"'
    if shell == "bash":
        return home / ".bashrc", 'export PATH="$HOME/.local/bin:$PATH"'
    if shell == "fish":
        config = Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config")
        return config / "fish/config.fish", "fish_add_path -g $HOME/.local/bin"
    if shell in {"sh", "dash", "ksh"}:
        return home / ".profile", 'export PATH="$HOME/.local/bin:$PATH"'
    return None


def path_configured(content: str, home: Path) -> bool:
    directory = r"(?:\$HOME|\$\{HOME\}|~|" + re.escape(str(home)) + r")/\.local/bin(?:[/\s\"':;]|$)"
    for line in content.splitlines():
        line = line.split("#", 1)[0].strip()
        if re.search(directory, line) and re.search(r"(?:\bPATH\s*=|\bfish_add_path\b|\bset\s+.*\b(?:PATH|fish_user_paths)\b)", line):
            return True
    return False


def configure_path(home: Path) -> None:
    """Explain PATH setup and request permission before editing one shell config."""
    print("To use torture, you need ~/.local/bin on your PATH.")
    shell = detect_shell()
    configuration = shell_configuration(home, shell)
    if configuration is None:
        print("Could not identify a supported shell. Add ~/.local/bin to PATH in your shell startup file.")
        return
    path, line = configuration
    print(f"Detected shell: {shell}; checking {path}")
    content = path.read_text() if path.exists() else ""
    if path_configured(content, home):
        print(f"PATH: already configured in {path}; no changes needed.")
        return
    print(f"Add this line to {path}:\n  {line}")
    if not sys.stdin.isatty():
        print("Non-interactive installation: shell configuration was not changed.")
        return
    try:
        answer = input(f"May I add this line to {path} for you? [y/N] ").strip().lower()
    except EOFError:
        answer = ""
    if answer not in {"y", "yes"}:
        print("Shell configuration was not changed. Please add the line yourself.")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as output:
        output.write(f"\n{PATH_MARKER}\n{line}\n")
    print(f"PATH: added to {path}. Open a new terminal or reload that file.")


def managed(path: Path) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    try:
        with path.open() as source:
            return source.readline().startswith("#!") and source.readline().strip() == MARKER
    except (OSError, UnicodeError):
        return False


def update(root: Path) -> None:
    def git(*args: str) -> str:
        return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()
    if git("rev-parse", "--show-toplevel") != str(root) or git("branch", "--show-current") != "main":
        raise RuntimeError("Update requires a Git checkout on the main branch.")
    if git("status", "--porcelain", "--untracked-files=normal"):
        raise RuntimeError("Update refused: the checkout has local changes.")
    subprocess.run(["git", "-C", str(root), "fetch", UPSTREAM, "main"], check=True)
    subprocess.run(["git", "-C", str(root), "merge", "--ff-only", "FETCH_HEAD"], check=True)


def install(root: Path, home: Path) -> Path:
    target = home / ".local/bin/torture"
    applications = home / ".local/applications"
    if target.is_symlink():
        previous = Path(os.readlink(target))
        if not previous.is_absolute():
            previous = Path(os.path.normpath(target.parent / previous))
        if previous.parent != applications or not managed(previous):
            raise RuntimeError(f"Refusing to replace an existing command: {target}")
    elif target.exists() and not managed(target):
        raise RuntimeError(f"Refusing to replace an existing command: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    # repr() quotes spaces, Unicode and embedded quote characters correctly.
    content = (f"#!/usr/bin/env python3\n{MARKER}\n"
               "import os\nimport sys\n"
               f"script = {str(root / 'torture.py')!r}\n"
               "os.execv(sys.executable, [sys.executable, script, *sys.argv[1:]])\n")
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=target.parent, prefix=".torture-",
                                         delete=False) as output:
            name = Path(output.name)
            output.write(content)
        name.chmod(0o755)
        os.replace(name, target)
    finally:
        if name is not None:
            name.unlink(missing_ok=True)
    # Remove only tagged old launchers, regardless of filename or interpreter.
    if applications.is_dir():
        for previous in applications.iterdir():
            if managed(previous):
                previous.unlink()
    return target


def uninstall(home: Path) -> None:
    """Remove only our launcher (and its managed legacy symlink target)."""
    target = home / ".local/bin/torture"
    previous = None
    if target.is_symlink():
        previous = Path(os.readlink(target))
        if not previous.is_absolute():
            previous = target.parent / previous
        previous = Path(os.path.normpath(previous.absolute()))
        if previous.parent != home / ".local/applications" or not managed(previous):
            raise RuntimeError(f"Refusing to delete an unrelated command: {target}")
    elif target.exists():
        if not managed(target):
            raise RuntimeError(f"Refusing to delete an unrelated command: {target}")
    else:
        print(f"Not installed: {target}")
        return
    target.unlink()
    if previous is not None:
        previous.unlink()
    print(f"Removed {target}")
    print("Kept shell PATH entries, other commands, the checkout, and custom tests.")
    print("Remove any old torture alias manually if one remains in your shell configuration.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--update", action="store_true", help="fast-forward a clean main checkout from upstream")
    action.add_argument("--delete", action="store_true", help="remove the managed torture launcher (requires --confirm)")
    parser.add_argument("--confirm", action="store_true", help="confirm --delete; never remove shared PATH directories")
    args = parser.parse_args()
    if args.delete != args.confirm:
        parser.error("uninstall requires both --delete and --confirm")
    root = Path(__file__).resolve().parent
    try:
        if args.delete:
            uninstall(Path.home())
            return 0
        if args.update:
            update(root)
            # A newer installer may have changed: rerun it after the fast-forward.
            os.execv(sys.executable, [sys.executable, str(root / "install.py")])
        target = install(root, Path.home())
        configure_path(Path.home())
        print(f"Installed {target}")
        if shutil.which("torture") != str(target):
            print("Add ~/.local/bin to PATH if needed. Remove any old torture alias from your shell config.")
        print("Update from the original repository: python3 install.py --update")
        return 0
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"install: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
