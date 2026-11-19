"""Submission files, README, norminette, and symbol checks."""
import fnmatch
import os
from pathlib import Path
import re
import shutil
from collections.abc import Callable

from ..checks import CheckSession
from ..runtime import RunnerError


def project_files(root: Path, *, ignore_hidden: bool = False):
    """Walk without following directory symlinks or entering Git metadata."""
    for parent, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(name for name in dirs if name != ".git" and not (ignore_hidden and name.startswith(".")))
        for name in sorted(dirs + names):
            path = Path(parent) / name
            if name != ".git" and not (ignore_hidden and name.startswith(".")):
                yield path


def allowed_path(key: str, relative: str) -> bool:
    path = Path(relative)
    if path.name == ".gitignore" or relative in ("Makefile", "README.md"):
        return True
    if key == "libft":
        return relative == "libft.h" or (len(path.parts) == 1 and fnmatch.fnmatchcase(relative, "ft_*.c"))
    if key == "printf":
        return ((len(path.parts) <= 2 and path.suffix in (".c", ".h"))
                or relative in ("libft/Makefile", "libft/README.md"))
    return relative in {f"get_next_line{suffix}{ext}"
                        for suffix in ("", "_utils", "_bonus", "_utils_bonus")
                        for ext in (".c", ".h") if not ("utils" in suffix and ext == ".h")}


def check_files(session: CheckSession, allowed: Callable[[str], bool]) -> None:
    root = session.ctx.options.directory
    bad = []
    for path in project_files(root, ignore_hidden=session.ctx.options.ignore_hidden):
        relative = path.relative_to(root).as_posix()
        if path.is_dir() and not path.is_symlink():
            if any(path.iterdir()) or (session.ctx.key == "printf" and relative == "libft"):
                continue
            reason = session.text("empty directory", "dossier vide")
        elif allowed(relative):
            continue
        elif any(part.startswith(".") for part in Path(relative).parts):
            reason = session.text("hidden file", "fichier caché")
        else:
            reason = session.text("unexpected submission file", "fichier à ne pas rendre")
        bad.append(f"{relative} ({reason})")
    session.check("KO" if bad else "OK", "Extra files", "Fichiers en trop",
                  f"{len(bad)} unexpected files" if bad else "none",
                  f"{len(bad)} fichiers inattendus" if bad else "aucun")
    session.details(bad)


def check_readme(session: CheckSession, *, algorithm: bool = False) -> None:
    path = session.ctx.options.directory / "README.md"
    if not path.is_file():
        session.check("KO", "README.md", "README.md", "missing (required by subject)", "absent (obligatoire)")
        return
    content = path.read_text(errors="replace")
    first = content.splitlines()[0] if content.splitlines() else ""
    missing = [label for label, pattern in (("Description", "description"), ("Instructions", "instructions?"),
                                            ("Resources", "resources?"))
               if not re.search(r"^#+\s*" + pattern, content, re.I | re.M)]
    if algorithm and not re.search(r"algorithm|algorithme", content, re.I):
        missing.append(session.text("algorithm explanation", "explication de l'algorithme"))
    if not re.fullmatch(r"([*_])This project has been created as part of the 42 curriculum by [^*_]+\1\s*", first):
        session.check("KO", "README.md", "README.md", "first line must be the italic 42 curriculum attribution",
                      "la première ligne doit être l'attribution 42 en italique")
    elif missing:
        session.check("WARN", "README.md", "README.md", "missing: " + ", ".join(missing),
                      "manquant : " + ", ".join(missing))
    else:
        session.check("OK", "README.md", "README.md", "attribution and required sections", "attribution et sections requises")


def check_norm(session: CheckSession) -> None:
    if not session.ctx.options.norm:
        session.check("SKIP", "Norminette", "Norminette", "disabled", "désactivée")
    elif not shutil.which("norminette"):
        session.check("SKIP", "Norminette", "Norminette", "not installed (pip install norminette)",
                      "non installée (pip install norminette)")
    else:
        status, output = session.capture(["norminette"], cwd=session.ctx.options.directory, name="norminette")
        errors = [line for line in output.splitlines() if re.match(r"\s*Error:", line)]
        bad = bool(status or errors or "Error!" in output)
        session.check("KO" if bad else "OK", "Norminette", "Norminette",
                      f"{len(errors)} errors; see checks/ logs" if bad else "no errors",
                      f"{len(errors)} erreurs ; voir checks/" if bad else "aucune erreur")
        if bad:
            session.details(errors or output.splitlines(), 6)


def symbols(session: CheckSession, artifacts: list[Path]) -> list[tuple[str, str, str]]:
    status, output = session.capture(["nm", "-A", *artifacts], name="symbols")
    if status:
        raise RunnerError(session.text("nm failed; see", "Échec de nm ; voir") + f" {session.directory}")
    result = []
    for line in output.splitlines():
        columns = line.split()
        if len(columns) >= 3 and re.fullmatch(r"[A-Za-z?]", columns[-2]):
            prefix = columns[0]
            owner = prefix[:-1] if prefix.endswith(":") else prefix.rpartition(":")[0]
            result.append((columns[-2], columns[-1], owner))
    return result


def check_symbols(session: CheckSession, entries: list[tuple[str, str, str]], *,
                  allowed: set[str], required: list[str], libft: bool = False) -> None:
    defined = {name for kind, name, _ in entries if kind != "U"}
    external = {name for kind, name, _ in entries if kind == "U"} - defined
    forbidden = sorted(external - allowed - {"__stack_chk_fail", "_GLOBAL_OFFSET_TABLE_"})
    session.check("KO" if forbidden else "OK", "External functions", "Fonctions externes",
                  "forbidden symbols" if forbidden else "only " + ", ".join(sorted(allowed)),
                  "symboles interdits" if forbidden else "uniquement " + ", ".join(sorted(allowed)))
    session.details([name + " (" + ", ".join(sorted({Path(owner).name for _, symbol, owner in entries
                                                     if symbol == name})) + ")" for name in forbidden])
    globals_ = [f"{name} ({Path(owner).name})" for kind, name, owner in entries if kind in "DBCRGSV"]
    session.check("KO" if globals_ else "OK", "Global variables", "Variables globales",
                  ", ".join(globals_) if globals_ else "none", ", ".join(globals_) if globals_ else "aucune")
    exported = {name for kind, name, _ in entries if kind == "T"}
    if libft:
        helpers = sorted(name for name in exported if not name.startswith("ft_"))
        session.check("WARN" if helpers else "OK", "Helper functions", "Fonctions auxiliaires",
                      "not static: " + ", ".join(helpers) if helpers else "all static",
                      "non static : " + ", ".join(helpers) if helpers else "toutes static")
    missing = sorted(set(required) - exported)
    session.check("KO" if missing else "OK", "Mandatory functions", "Fonctions obligatoires",
                  f"{len(required) - len(missing)}/{len(required)} present" + (": missing " + ", ".join(missing) if missing else ""),
                  f"{len(required) - len(missing)}/{len(required)} présentes" + (" : absentes " + ", ".join(missing) if missing else ""))
