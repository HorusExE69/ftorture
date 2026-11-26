"""Submission files, README, norminette, and symbol checks."""
import fnmatch
import os
from pathlib import Path
import re
import shlex
import shutil
from collections.abc import Callable

from ..checks import CheckSession
from ..runtime import RunnerError
from .gitignore import GitIgnore


def project_files(root: Path, *, ignore_hidden: bool = False, gitignore: bool = True,
                  skipped: list[Path] | None = None):
    """Walk without following directory symlinks or entering Git metadata.

    What the .gitignore files of the folder ignore is never pushed, so it is not
    part of the submission: it is left out (and its folders are not entered).
    `skipped` collects those top-level ignored entries.
    """
    rules = GitIgnore(root) if gitignore else None
    for parent, dirs, names in os.walk(root, followlinks=False):
        here = Path(parent)
        if rules:
            rules.enter(here)

        def kept(name: str, is_dir: bool) -> bool:
            if name == ".git" or (ignore_hidden and name.startswith(".")):
                return False
            if rules and rules.ignored(here / name, is_dir):
                if skipped is not None:
                    skipped.append(here / name)
                return False
            return True
        dirs[:] = sorted(name for name in dirs if kept(name, True))
        files = [name for name in names if kept(name, (here / name).is_dir())]
        for name in sorted(dirs + files):
            yield here / name


def find_file(root: Path, name: str, *, max_depth: int = 4, limit: int = 20000,
              ignore_hidden: bool = False) -> Path | None:
    """Shallowest `name` under root (root first), skipping .git and what the
    .gitignore files ignore. Bounded, so a home directory stays fast."""
    rules = GitIgnore(root)
    level, seen = [root], 0
    for _ in range(max_depth + 1):
        found, deeper = [], []
        for directory in level:
            rules.enter(directory)
            try:
                entries = sorted(os.scandir(directory), key=lambda entry: entry.name)
            except OSError:
                continue
            for entry in entries:
                seen += 1
                if seen > limit:
                    return min(found, default=None)
                if entry.name == ".git" or (ignore_hidden and entry.name.startswith(".")):
                    continue
                is_dir = entry.is_dir(follow_symlinks=False)
                if rules.ignored(Path(entry.path), is_dir):
                    continue
                if is_dir:
                    deeper.append(Path(entry.path))
                elif entry.name == name and entry.is_file():
                    found.append(Path(entry.path))
        if found:
            return min(found)
        level = deeper
    return None


def header_dirs(root: Path, *, ignore_hidden: bool = False) -> list[Path]:
    """Every folder holding a submitted .h: the -I list of a project with includes/."""
    return sorted({path.parent for path in project_files(root, ignore_hidden=ignore_hidden)
                   if path.suffix == ".h" and path.is_file()} | {root})


def allowed_path(key: str, relative: str) -> bool:
    path = Path(relative)
    if path.name == ".gitignore" or relative in ("Makefile", "README.md"):
        return True
    if key == "libft":
        # libft.h and ft_*.c, at the root or in subfolders (srcs/, includes/...)
        return path.name == "libft.h" or fnmatch.fnmatchcase(path.name, "ft_*.c")
    if key == "push_swap":
        # Subject: Makefile, *.h, *.c (and a libft folder with its Makefile).
        return path.suffix in (".c", ".h") or relative == "libft/Makefile"
    if key == "printf":
        return path.suffix in (".c", ".h") or relative in ("libft/Makefile", "libft/README.md")
    return relative in {f"get_next_line{suffix}{ext}"
                        for suffix in ("", "_utils", "_bonus", "_utils_bonus")
                        for ext in (".c", ".h") if not ("utils" in suffix and ext == ".h")}


def check_files(session: CheckSession, allowed: Callable[[str], bool]) -> None:
    root = session.ctx.options.directory
    bad = []
    skipped: list[Path] = []
    for path in project_files(root, ignore_hidden=session.ctx.options.ignore_hidden, skipped=skipped):
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
    note_en = f" ({len(skipped)} ignored by .gitignore)" if skipped else ""
    note_fr = f" ({len(skipped)} ignorés via .gitignore)" if skipped else ""
    session.check("KO" if bad else "OK", "Extra files", "Fichiers en trop",
                  (f"{len(bad)} unexpected files" if bad else "none") + note_en,
                  (f"{len(bad)} fichiers inattendus" if bad else "aucun") + note_fr, soft=True)
    session.details(bad)


def check_readme(session: CheckSession, *, algorithm: bool = False) -> None:
    path = session.ctx.options.directory / "README.md"
    if not path.is_file():
        session.check("KO", "README.md", "README.md", "missing (required by subject)", "absent (obligatoire)", soft=True)
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
                      "la première ligne doit être l'attribution 42 en italique", soft=True)
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
        # Only the submitted C files: nothing .gitignore'd (or hidden with --no-hidden).
        directory = session.ctx.options.directory
        sources = [path.relative_to(directory).as_posix() for path in project_files(
                   directory, ignore_hidden=session.ctx.options.ignore_hidden)
                   if path.suffix in (".c", ".h") and path.is_file() and not path.is_symlink()]
        if not sources:
            session.check("SKIP", "Norminette", "Norminette", "no .c or .h file", "aucun fichier .c ou .h")
            return
        status, output = session.capture(["norminette", *sources], cwd=directory, name="norminette")
        errors = [line for line in output.splitlines() if re.match(r"\s*Error:", line)]
        bad = bool(status or errors or "Error!" in output)
        session.check("KO" if bad else "OK", "Norminette", "Norminette",
                      f"{len(errors)} errors; see checks/ logs" if bad else "no errors",
                      f"{len(errors)} erreurs ; voir checks/" if bad else "aucune erreur", soft=True)
        if bad:
            session.details(errors or output.splitlines(), 6)


def symbols(session: CheckSession, artifacts: list[Path]) -> list[tuple[str, str, str]]:
    status, output = session.capture(["nm", "-A", *artifacts], name="symbols")
    if status:
        raise RunnerError(session.text("nm failed; see", "Échec de nm ; voir") + f" {session.directory}")
    result = []
    for line in output.splitlines():
        match = re.match(r"^(.+?):(?:[0-9a-fA-F]+\s+|\s+)([A-Za-z?])\s+(\S+)$", line)
        if match:
            owner = match.group(1).rpartition(":")[2] or match.group(1)
            result.append((match.group(2), match.group(3), owner))
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


def check_compile_commands(session: CheckSession, dry: str) -> None:
    """Flags and compiler of every `cc -c x.c` line printed by `make -nB`."""
    commands = []
    for line in dry.splitlines():
        try:
            args = shlex.split(line)
        except ValueError:
            continue
        if "-c" in args and any(arg.endswith(".c") for arg in args):
            commands.append(args)
    if not commands:
        session.check("WARN", "Compiler flags", "Flags de compilation", "no compile command detected", "aucune compilation détectée")
    else:
        flags_ok = all({"-Wall", "-Wextra", "-Werror"} <= set(args) for args in commands)
        cc_ok = all(args[0].rsplit("/", 1)[-1] == "cc" for args in commands)
        session.check("OK" if flags_ok else "KO", "Compiler flags", "Flags de compilation",
                      "-Wall -Wextra -Werror required on every file", "-Wall -Wextra -Werror requis sur chaque fichier", soft=True)
        session.check("OK" if cc_ok else "KO", "Compiler", "Compilateur", "cc required by subject", "cc imposé par le sujet", soft=True)
        if any("-std=c99" in args for args in commands):
            session.check("KO", "Flag -std=c99", "Flag -std=c99", "forbidden by subject", "interdit par le sujet", soft=True)


def compiled_sources(root: Path, dry: str) -> set[str]:
    """Project-relative .c files of every `cc -c` line printed by `make -nB`.
    Recursive makes (libft/) print paths relative to their own folder: those
    are matched by their trailing path inside the project."""
    files = [path.relative_to(root).as_posix() for path in project_files(root) if path.suffix == ".c"]
    found: set[str] = set()
    for line in dry.splitlines():
        try:
            args = shlex.split(line)
        except ValueError:
            continue
        if "-c" not in args:
            continue
        for arg in args:
            if not arg.endswith(".c"):
                continue
            name = Path(arg).as_posix()     # also drops a leading ./
            direct = Path(arg) if arg.startswith("/") else root / arg
            if direct.is_file() and direct.resolve().is_relative_to(root.resolve()):
                found.add(direct.resolve().relative_to(root.resolve()).as_posix())
                continue
            found.update(file for file in files if file == name or file.endswith("/" + name))
    return found


def bonus_header_closure(root: Path, sources: set[str]) -> set[str]:
    """Project headers reached by #include "..." from these sources, transitively."""
    from .includes import include_list
    dirs = [d.relative_to(root).as_posix() for d in header_dirs(root)]
    seen: set[str] = set()
    todo = list(sources)
    while todo:
        current = todo.pop()
        path = root / current
        try:
            includes = include_list(path.read_text(errors="replace"))
        except OSError:
            continue
        for kind, name in includes:
            if kind != "usr":
                continue
            for base in (path.parent, *(root / d for d in dirs)):
                candidate = (base / name)
                if candidate.is_file() and candidate.resolve().is_relative_to(root.resolve()):
                    relative = candidate.resolve().relative_to(root.resolve()).as_posix()
                    if relative not in seen:
                        seen.add(relative)
                        todo.append(relative)
                    break
    return seen


def check_bonus_files(session: CheckSession, all_dry: str, bonus_dry: str, *, required: bool = True) -> None:
    """The common 42 rule: bonuses go in *_bonus.c / *_bonus.h files. Only the
    files the bonus build uses and the mandatory one does not are concerned
    (shared helpers may keep their name)."""
    root = session.ctx.options.directory
    mandatory = compiled_sources(root, all_dry)
    bonus = compiled_sources(root, bonus_dry)
    only_sources = sorted(bonus - mandatory)
    only_headers = sorted(bonus_header_closure(root, set(only_sources))
                          - bonus_header_closure(root, mandatory))
    bad = [name for name in only_sources if not name.endswith("_bonus.c")]
    bad += [name for name in only_headers if not name.endswith("_bonus.h")]
    if not bonus:
        session.check("WARN", "Bonus file names", "Noms des fichiers bonus", "no compile command in make -nB bonus",
                      "aucune compilation dans make -nB bonus")
        return
    if not only_sources and not only_headers:
        session.check("OK", "Bonus file names", "Noms des fichiers bonus", "the bonus uses no file of its own",
                      "le bonus n'a pas de fichier à lui")
        return
    status = ("KO" if required else "WARN") if bad else "OK"
    note_en = "" if required else " (this subject lists *.c / *.h for the bonus)"
    note_fr = "" if required else " (ce sujet liste *.c / *.h pour le bonus)"
    session.check(status, "Bonus file names", "Noms des fichiers bonus",
                  (f"{len(bad)} bonus-only files without _bonus" if bad
                   else f"{len(only_sources) + len(only_headers)} bonus-only files, all *_bonus.c / *_bonus.h") + note_en,
                  (f"{len(bad)} fichiers propres au bonus sans _bonus" if bad
                   else f"{len(only_sources) + len(only_headers)} fichiers propres au bonus, tous en *_bonus.c / *_bonus.h") + note_fr,
                  soft=True)
    session.details(bad)
