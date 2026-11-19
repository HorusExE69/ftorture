"""Subject checks for the two Makefile/archive projects."""
import re
import shlex
from typing import TYPE_CHECKING

from ..checks import CheckSession
from ..runtime import Context, RunnerError
from .common import allowed_path, check_files, check_readme, check_norm, check_symbols, symbols
from .includes import IncludeAnalysis
from .prototypes import check_prototypes, expected_prototypes

if TYPE_CHECKING:
    from ..projects.archive import ArchiveProject


def archive_checks(ctx: Context, project: "ArchiveProject", *, algorithm: bool = False,
                   linked_list: bool = False) -> None:
    session = CheckSession(ctx)
    report = session.report
    archive = ctx.options.directory / project.archive

    def make(*args: str) -> tuple[int, str]:
        return session.capture(["make", "--no-print-directory", "-C", ctx.options.directory, *args], name="make")

    def relink(output: str) -> bool:
        return bool(re.search(r"(^|[\s/])(cc|gcc|clang|ar)\s", output, re.M))

    try:
        report.section("STRUCTURE & MAKEFILE")
        project.make(ctx, "fclean", log="checks-fclean.log")
        session.check("OK", "Files to submit", "Fichiers à rendre", f"Makefile, {project.header}, C sources",
                      f"Makefile, {project.header}, sources C")
        check_files(session, lambda path: allowed_path(project.key, path))
        missing = [rule for rule in (project.archive, "all", "clean", "fclean", "re") if make("-n", rule)[0]]
        if not re.search(r"^\s*NAME\s*:?=", (ctx.options.directory / "Makefile").read_text(errors="replace"), re.M):
            missing.append("$(NAME)")
        session.check("KO" if missing else "OK", "Makefile rules", "Règles Makefile",
                      "missing: " + ", ".join(missing) if missing else "$(NAME) all clean fclean re",
                      "manquantes : " + ", ".join(missing) if missing else "$(NAME) all clean fclean re")
        bonus = project.has_bonus(ctx) if project.key == "printf" else False
        if project.key == "printf":
            session.check("OK" if bonus else "SKIP", "Bonus rule", "Règle bonus",
                          "present" if bonus else "missing; bonus not tested",
                          "présente" if bonus else "absente ; bonus non testé")
        _, dry = make("-nB", "all")
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
                          "-Wall -Wextra -Werror required on every file", "-Wall -Wextra -Werror requis sur chaque fichier")
            session.check("OK" if cc_ok else "KO", "Compiler", "Compilateur", "cc required by subject", "cc imposé par le sujet")
            if any("-std=c99" in args for args in commands):
                session.check("KO", "Flag -std=c99", "Flag -std=c99", "forbidden by subject", "interdit par le sujet")
        archive_status = "KO" if "libtool" in dry else "OK" if re.search(r"(^|[\s/])ar\s", dry, re.M) else "WARN"
        session.check(archive_status, "Archive", "Archive", "use ar, not libtool", "utiliser ar, pas libtool")
        project.build_archive(ctx)
        _, output = make("-n", "all")
        _, output_archive = make("-n", project.archive)
        session.check("KO" if relink(output + output_archive) else "OK", "Relink", "Relink",
                      "make must not rebuild unchanged files", "make ne doit pas recompiler sans changement")
        if bonus:
            try:
                project.build_archive(ctx, "bonus")
            except RunnerError:
                session.check("KO", "make bonus", "make bonus", "build failed; see make.log", "échec ; voir make.log")
            else:
                _, output = make("-n", "bonus")
                session.check("KO" if relink(output) else "OK", "Bonus relink", "Relink bonus",
                              "make bonus must not rebuild unchanged files", "make bonus ne doit pas recompiler sans changement")
        project.build_archive(ctx)
        clean_status, _ = make("clean")
        objects = list(ctx.options.directory.rglob("*.o"))
        clean_result = "KO" if clean_status or objects else "WARN" if not archive.is_file() else "OK"
        session.check(clean_result, "make clean", "make clean", "must remove objects and keep archive",
                      "doit supprimer les objets et garder l'archive")
        fclean_status, _ = make("fclean")
        session.check("KO" if fclean_status or archive.exists() else "OK", "make fclean", "make fclean",
                      "must remove archive", "doit supprimer l'archive")
        project.build_archive(ctx)
        check_readme(session, algorithm=algorithm)
        report.section("CODE")
        check_norm(session)
        IncludeAnalysis(session).run()
        check_symbols(session, symbols(session, [archive]), allowed={"malloc", "free", "write"},
                      required=[name for name, _, _ in expected_prototypes(session)], libft=linked_list)
        check_prototypes(session, project.header, project.subject, linked_list=linked_list)
    finally:
        report.write(ctx.checks_file)
