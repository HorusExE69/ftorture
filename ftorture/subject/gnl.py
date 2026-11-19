"""Native get_next_line compilation, file, code, and prototype checks."""
from pathlib import Path

from ..checks import CheckSession
from ..runtime import Context
from .common import allowed_path, check_files, check_norm, check_readme, check_symbols, symbols
from .includes import IncludeAnalysis
from .prototypes import check_prototypes


def gnl_checks(ctx: Context, header: str, subject: str) -> None:
    session = CheckSession(ctx)
    report = session.report
    try:
        report.section(session.text("FILES", "FICHIERS"))
        mandatory = ("get_next_line.c", "get_next_line_utils.c", "get_next_line.h")
        bonus = ("get_next_line_bonus.c", "get_next_line_utils_bonus.c", "get_next_line_bonus.h")
        missing = [name for name in mandatory if not (ctx.options.directory / name).is_file()]
        session.check("KO" if missing else "OK", "Files to submit", "Fichiers à rendre",
                      "missing: " + ", ".join(missing) if missing else ", ".join(mandatory),
                      "absents : " + ", ".join(missing) if missing else ", ".join(mandatory))
        count = sum((ctx.options.directory / name).is_file() for name in bonus)
        session.check("OK" if count == 3 else "WARN" if count else "SKIP", "Bonus files", "Fichiers bonus",
                      f"{count}/3 bonus files", f"{count}/3 fichiers bonus")
        check_files(session, lambda path: allowed_path("gnl", path))
        check_readme(session, algorithm=True)
        report.section("COMPILATION")

        def compile_set(key: str, names: tuple[str, ...], definitions: list[str]) -> list[Path]:
            out = session.directory / key
            out.mkdir(exist_ok=True)
            objects = []
            for name in names:
                target = out / (name.removesuffix(".c") + ".o")
                if not ctx.compile(["-Wall", "-Wextra", "-Werror", *definitions,
                                    f"-I{ctx.options.directory}", "-c", ctx.options.directory / name, "-o", target],
                                   out / (name + ".log")):
                    return []
                objects.append(target)
            return objects

        objects = compile_set("mandatory-42", mandatory[:2], ["-D", "BUFFER_SIZE=42"])
        defaults = compile_set("mandatory-default", mandatory[:2], [])
        session.check("OK" if objects else "KO", "-D BUFFER_SIZE=42", "-D BUFFER_SIZE=42",
                      "compile with subject flags", "compilation avec les flags du sujet")
        session.check("OK" if defaults else "KO", "Without -D BUFFER_SIZE", "Sans -D BUFFER_SIZE",
                      "default value must compile", "la valeur par défaut doit compiler")
        bonus_objects = compile_set("bonus-42", bonus[:2], ["-D", "BUFFER_SIZE=42"]) if count == 3 else []
        if count == 3:
            session.check("OK" if bonus_objects else "KO", "Bonus compilation", "Compilation bonus",
                          "bonus source files", "sources bonus")
        report.section("CODE")
        check_norm(session)
        IncludeAnalysis(session).run()
        if objects:
            check_symbols(session, symbols(session, objects), allowed={"read", "malloc", "free"},
                          required=["get_next_line"])
        if bonus_objects:
            entries = symbols(session, bonus_objects)
            check_symbols(session, entries, allowed={"read", "malloc", "free"}, required=["get_next_line"])
            statics = {name for kind, name, _ in entries if kind in "bd"}
            session.check("OK" if len(statics) <= 1 else "KO", "Bonus static variable", "Variable static bonus",
                          f"{len(statics)} (at most one allowed)", f"{len(statics)} (une seule autorisée)")
        check_prototypes(session, header, subject)
    finally:
        report.write(ctx.checks_file)
