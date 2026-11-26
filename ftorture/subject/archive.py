"""Subject checks for the two Makefile/archive projects."""
import re
from typing import TYPE_CHECKING

from ..checks import CheckSession
from ..runtime import Context, RunnerError
from .common import (allowed_path, check_bonus_files, check_compile_commands, check_files, check_readme, check_norm,
                     check_symbols, symbols)
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
                      "manquantes : " + ", ".join(missing) if missing else "$(NAME) all clean fclean re", soft=True)
        bonus = project.has_bonus(ctx) if project.key == "printf" else False
        if project.key == "printf":
            session.check("OK" if bonus else "SKIP", "Bonus rule", "Règle bonus",
                          "present" if bonus else "missing; bonus not tested",
                          "présente" if bonus else "absente ; bonus non testé")
        _, dry = make("-nB", "all")
        check_compile_commands(session, dry)
        if bonus or (project.key != "printf" and project.has_bonus(ctx)):
            check_bonus_files(session, dry, make("-nB", "bonus")[1])
        archive_status = "KO" if "libtool" in dry else "OK" if re.search(r"(^|[\s/])ar\s", dry, re.M) else "WARN"
        session.check(archive_status, "Archive", "Archive", "use ar, not libtool", "utiliser ar, pas libtool", soft=True)
        project.build_archive(ctx)
        _, output = make("-n", "all")
        _, output_archive = make("-n", project.archive)
        session.check("KO" if relink(output + output_archive) else "OK", "Relink", "Relink",
                      "make must not rebuild unchanged files", "make ne doit pas recompiler sans changement", soft=True)
        if bonus:
            try:
                project.build_archive(ctx, "bonus")
            except RunnerError:
                session.check("KO", "make bonus", "make bonus", "build failed; see make.log", "échec ; voir make.log")
            else:
                _, output = make("-n", "bonus")
                session.check("KO" if relink(output) else "OK", "Bonus relink", "Relink bonus",
                              "make bonus must not rebuild unchanged files", "make bonus ne doit pas recompiler sans changement",
                              soft=True)
        project.build_archive(ctx)
        clean_status, _ = make("clean")
        objects = list(ctx.options.directory.rglob("*.o"))
        clean_result = "KO" if clean_status or objects else "WARN" if not archive.is_file() else "OK"
        session.check(clean_result, "make clean", "make clean", "must remove objects and keep archive",
                      "doit supprimer les objets et garder l'archive", soft=True)
        fclean_status, _ = make("fclean")
        session.check("KO" if fclean_status or archive.exists() else "OK", "make fclean", "make fclean",
                      "must remove archive", "doit supprimer l'archive", soft=True)
        project.build_archive(ctx)
        check_readme(session, algorithm=algorithm)
        report.section("CODE")
        check_norm(session)
        IncludeAnalysis(session).run()
        libft = ctx.options.directory / "libft/libft.a"
        if project.key == "printf" and libft.is_file():
            # The subject allows a libft/ folder: its functions are not external,
            # and its own externals are checked with the same rule.
            own = symbols(session, [archive])
            defined = {name for kind, name, _ in own if kind != "U"}
            from_libft = sorted({name for kind, name, _ in own if kind == "U"} - defined
                                & {name for kind, name, _ in symbols(session, [libft]) if kind == "T"})
            session.check("KO" if from_libft else "OK", "libft in the archive", "libft dans l'archive",
                          ("missing from the archive: " + ", ".join(from_libft) + " (a program linked with "
                           "libftprintf.a alone does not build: cp libft/libft.a $(NAME) before ar rcs)")
                          if from_libft else "the libft functions used are inside the archive",
                          ("absentes de l'archive : " + ", ".join(from_libft) + " (un programme lié avec "
                           "libftprintf.a seul ne compile pas : cp libft/libft.a $(NAME) avant ar rcs)")
                          if from_libft else "les fonctions de la libft utilisées sont dans l'archive")
            entries = symbols(session, [archive, libft])
        else:
            entries = symbols(session, [archive])
        check_symbols(session, entries, allowed={"malloc", "free", "write"},
                      required=[name for name, _, _ in expected_prototypes(session)], libft=linked_list)
        check_prototypes(session, project.header, project.subject, linked_list=linked_list)
    finally:
        report.write(ctx.checks_file)
