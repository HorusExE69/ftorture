"""push_swap subject checks: Makefile, files, README, code and valgrind."""
import re
import shutil
from typing import TYPE_CHECKING

from ..checks import CheckSession
from ..runtime import Context, RunnerError
from .common import (allowed_path, check_bonus_files, check_compile_commands, check_files, check_norm, check_readme,
                     check_symbols, symbols)
from .includes import IncludeAnalysis

if TYPE_CHECKING:
    from ..projects.push_swap import PushSwapProject

ALLOWED = {"read", "write", "malloc", "free", "exit"}

# (arguments, stdin for checker); the inputs every valgrind run uses
LEAK_RUNS = (
    ("push_swap", ["5", "-3", "42", "0", "17", "-8", "9", "1", "33", "-21"], None),
    ("push_swap", ["--simple", "4", "1", "3", "2", "5"], None),
    ("push_swap", ["--medium", *map(str, range(40, 0, -3))], None),
    ("push_swap", ["--complex", *map(str, range(40, 0, -3))], None),
    ("push_swap", ["--bench", "--adaptive", "8", "2", "6", "4", "0"], None),
    ("push_swap", ["1", "2", "3"], None),
    ("push_swap", ["1", "a", "3"], None),
    ("push_swap", ["1", "2", "1"], None),
    ("push_swap", ["2147483648"], None),
    ("push_swap", [], None),
    ("checker", ["2", "1", "3"], "sa\n"),
    ("checker", ["2", "1", "3"], "pb\n"),
    ("checker", ["2", "1", "3"], "sa\nfoo\n"),
    ("checker", ["1", "1"], ""),
)


def readme_group(session: CheckSession) -> None:
    path = session.ctx.options.directory / "README.md"
    if not path.is_file():
        return
    content = path.read_text(errors="replace")
    first = content.splitlines()[0] if content.splitlines() else ""
    logins = [name for name in re.split(r"\s*(?:,|\band\b|\bet\b|&)\s*",
                                       first.rpartition(" by ")[2].strip("*_ \t")) if name]
    contribution = re.search(r"contribut|répartition|division of work|who did", content, re.I)
    session.check("OK" if len(logins) >= 2 and contribution else "WARN", "Group project", "Projet de groupe",
                  "2 logins and each one's contribution" if len(logins) >= 2 and contribution
                  else "README needs both logins and each learner's contribution",
                  "2 logins et la contribution de chacun" if len(logins) >= 2 and contribution
                  else "le README doit citer les 2 logins et la contribution de chacun")


def valgrind(session: CheckSession, bonus: bool) -> None:
    session.report.section(session.text("MEMORY", "MÉMOIRE"))
    if not shutil.which("valgrind"):
        session.check("SKIP", "Leaks (valgrind)", "Fuites (valgrind)", "valgrind not installed",
                      "valgrind non installé")
        return
    from concurrent.futures import ThreadPoolExecutor
    from ..sanitize import SLOTS
    directory = session.ctx.options.directory
    errors, reachable = [], []
    runs = [run for run in LEAK_RUNS if run[0] != "checker" or bonus]
    logs = []
    for _ in runs:
        session.sequence += 1
        logs.append(session.directory / f"{session.sequence:03d}-valgrind.log")
    ctx = session.ctx

    def memcheck(job) -> None:
        (program, args, stdin), log = job
        command = ["valgrind", "--leak-check=full", "--show-leak-kinds=all", "--track-fds=no",
                   f"--log-file={log}", f"./{program}", *args]
        with SLOTS:
            ctx.command(command, cwd=directory, log=log.with_name(log.name.replace("valgrind", "output")),
                        timeout=60, stdin=stdin)
        ctx.shard_done()
    # every run under valgrind at the same time, one per free core
    ctx.shard_started(len(runs))
    with ThreadPoolExecutor(len(runs) + 1) as pool:
        ctx.wait(pool.submit(lambda: list(pool.map(memcheck, zip(runs, logs)))))
    for (program, args, stdin), log in zip(runs, logs):
        output = log.read_text(errors="replace") if log.is_file() else ""
        shown = f"./{program} {' '.join(args)}".strip() + (f" < {stdin!r}" if stdin is not None else "")

        def lost(kind: str) -> int:
            match = re.search(kind + r" lost: ([\d,]+) bytes", output)
            return int(match.group(1).replace(",", "")) if match else 0
        summary = re.search(r"ERROR SUMMARY: (\d+) errors", output)
        problems = []
        if lost("definitely") or lost("indirectly"):
            problems.append(session.text(f"{lost('definitely') + lost('indirectly')} bytes lost",
                                         f"{lost('definitely') + lost('indirectly')} octets perdus"))
        if re.search(r"Invalid (read|write|free)|uninitialised|Mismatched free", output):
            problems.append(session.text("invalid memory access", "accès mémoire invalide"))
        elif summary and int(summary.group(1)) and not problems:
            problems.append(f"{summary.group(1)} " + session.text("errors", "erreurs"))
        if problems:
            errors.append(f"{shown} ({', '.join(problems)})")
        match = re.search(r"still reachable: ([\d,]+) bytes", output)
        if match and match.group(1) != "0":
            reachable.append(f"{shown} ({match.group(1)} " + session.text("bytes", "octets") + ")")
    session.check("KO" if errors else "OK", "Leaks (valgrind)", "Fuites (valgrind)",
                  f"{len(errors)} runs with errors" if errors else "no leak, no invalid access",
                  f"{len(errors)} exécutions en erreur" if errors else "aucune fuite ni accès invalide")
    session.details(errors, 8)
    session.check("WARN" if reachable else "OK", "Still reachable", "Still reachable",
                  "memory not freed before exit" if reachable else "all heap blocks freed",
                  "mémoire non libérée avant exit" if reachable else "tout est libéré")
    session.details(reachable, 4)


def push_swap_checks(ctx: Context, project: "PushSwapProject") -> None:
    session = CheckSession(ctx)
    report = session.report
    directory = ctx.options.directory

    def make(*args: str) -> tuple[int, str]:
        return session.capture(["make", "--no-print-directory", "-C", directory, *args], name="make")

    def relink(output: str) -> bool:
        return bool(re.search(r"(^|[\s/])(cc|gcc|clang)\s", output, re.M))

    def built() -> list:
        # Only the objects this Makefile made: a visualizer or a CMake build
        # left in the folder is not part of push_swap.
        return sorted(set(directory.rglob("*.o")) - foreign)

    try:
        report.section("STRUCTURE & MAKEFILE")
        project.make(ctx, "fclean", log="checks-fclean.log")
        foreign = set(directory.rglob("*.o"))
        check_files(session, lambda path: allowed_path(project.key, path))
        missing = [rule for rule in ("push_swap", "all", "clean", "fclean", "re") if make("-n", rule)[0]]
        if not re.search(r"^\s*NAME\s*:?=", (directory / "Makefile").read_text(errors="replace"), re.M):
            missing.append("$(NAME)")
        session.check("KO" if missing else "OK", "Makefile rules", "Règles Makefile",
                      "missing: " + ", ".join(missing) if missing else "$(NAME) all clean fclean re",
                      "manquantes : " + ", ".join(missing) if missing else "$(NAME) all clean fclean re", soft=True)
        bonus = project.has_bonus(ctx)
        session.check("OK" if bonus else "SKIP", "Bonus rule", "Règle bonus",
                      "present (checker)" if bonus else "missing; checker not tested",
                      "présente (checker)" if bonus else "absente ; checker non testé")
        _, dry = make("-nB", "all")
        check_compile_commands(session, dry)
        if bonus:
            # The general rule says *_bonus.{c,h}; this subject's checker table
            # lists "*.h, *.c", so only a warning.
            check_bonus_files(session, dry, make("-nB", "bonus")[1], required=False)
        project.build(ctx)
        _, output = make("-n", "all")
        session.check("KO" if relink(output) else "OK", "Relink", "Relink",
                      "make must not rebuild unchanged files", "make ne doit pas recompiler sans changement", soft=True)
        if bonus:
            try:
                project.build(ctx, "bonus")
            except RunnerError:
                bonus = False
                session.check("KO", "make bonus", "make bonus", "build failed or no ./checker; see make.log",
                              "échec ou pas de ./checker ; voir make.log")
            else:
                _, output = make("-n", "bonus")
                session.check("KO" if relink(output) else "OK", "Bonus relink", "Relink bonus",
                              "make bonus must not rebuild unchanged files",
                              "make bonus ne doit pas recompiler sans changement", soft=True)
        clean_status, _ = make("clean")
        left = built()
        session.check("KO" if clean_status or left else "WARN" if not (directory / "push_swap").is_file() else "OK",
                      "make clean", "make clean", "must remove objects and keep push_swap",
                      "doit supprimer les objets et garder push_swap", soft=True)
        fclean_status, _ = make("fclean")
        binaries = [name for name in ("push_swap", "checker") if (directory / name).exists()]
        session.check("KO" if fclean_status or binaries else "OK", "make fclean", "make fclean",
                      "must remove push_swap" + (" and checker" if bonus else ""),
                      "doit supprimer push_swap" + (" et checker" if bonus else ""), soft=True)
        check_readme(session, algorithm=True)
        readme_group(session)
        report.section("CODE")
        check_norm(session)
        IncludeAnalysis(session).run()
        project.build(ctx)
        if bonus:
            project.build(ctx, "bonus")
        objects = built()
        if objects:
            check_symbols(session, symbols(session, objects), allowed=ALLOWED, required=["main"])
            statics = sorted({f"{name} ({owner.rsplit('/', 1)[-1]})" for kind, name, owner
                              in symbols(session, objects) if kind in "bd" and "." not in name})
            session.check("WARN" if statics else "OK", "Static globals", "Globales static",
                          ", ".join(statics) if statics else "none (global variables are forbidden)",
                          ", ".join(statics) if statics else "aucune (variables globales interdites)")
        else:
            session.check("WARN", "External functions", "Fonctions externes", "no object file found",
                          "aucun fichier objet trouvé")
        valgrind(session, bonus)
    finally:
        report.write(ctx.checks_file)
