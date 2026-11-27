"""CLI dispatch and run lifecycle. Project-specific behavior lives in projects/."""
import argparse
from contextlib import contextmanager
import fcntl
from pathlib import Path
import platform
import shutil
import signal
import sys

from .language import default_language, text
from .registry import load_registry
from .projects.base import Project
from .runtime import Context, Options, RunnerError
from .ui import interactive, run_footer, run_header

ROOT = Path(__file__).resolve().parent.parent


def positive(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected a positive integer") from exc
    if number < 1:
        raise argparse.ArgumentTypeError("expected a positive integer")
    return number


def unsigned(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected an unsigned 32-bit integer") from exc
    if not 0 <= number <= 0xFFFFFFFF:
        raise argparse.ArgumentTypeError("expected an unsigned 32-bit integer")
    return number


def percentage(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected a percentage between 1 and 100") from exc
    if not 1 <= number <= 100:
        raise argparse.ArgumentTypeError("expected a percentage between 1 and 100")
    return number


def normalize_efficiency_args(argv: list[str]) -> list[str]:
    normalized: list[str] = []
    index = 0
    while index < len(argv):
        token = argv[index]
        if token == "--":
            normalized.extend(argv[index:])
            break
        if token.startswith("--efficiency="):
            normalized.append("--target=" + token.split("=", 1)[1])
            index += 1
        elif token in ("-e", "--efficiency") and index + 1 < len(argv) and argv[index + 1].isdigit():
            normalized.append(f"--target={argv[index + 1]}")
            index += 2
        else:
            normalized.append(token)
            index += 1
    return normalized


def parser(lang: str) -> argparse.ArgumentParser:
    def t(en: str, fr: str) -> str:
        return text(lang, en, fr)
    result = argparse.ArgumentParser(prog="torture", description=t(
        "Test 42 C and Python projects with ftorture.", "Tester les projets 42 C et Python avec ftorture."))
    result.add_argument("target", nargs="?", help=t("project name or directory", "nom du projet ou dossier"))
    result.add_argument("directory", nargs="?", help=t("project directory", "dossier du projet"))
    result.add_argument("--lang", choices=("en", "fr"), default=lang, help=t("output language", "langue"))
    result.add_argument("--list-projects", action="store_true", help=t("list supported projects", "lister les projets"))
    result.add_argument("--custom-tests-dir", type=Path, help=t("directory of user test manifests", "dossier des tests personnalisés"))
    result.add_argument("-s", "--speculative", action="store_true", help=t("count ▲ as failures", "compter les ▲ comme erreurs"))
    result.add_argument("-v", "--verbose", action="store_true", help=t("show all failure details", "afficher tous les détails"))
    result.add_argument("-e", "--efficiency", action="store_true", help=t(
        "compare each function with a perfect time, optional target N%% (default: 50)",
        "comparer chaque fonction à un temps parfait, objectif N %% optionnel (défaut : 50)"))
    result.add_argument("-t", "--target", dest="efficiency_target", type=percentage, metavar="N", help=t(
        "efficiency target in %% (1-100); turns -e on", "objectif d'efficacité en %% (1-100) ; active -e"))
    result.add_argument("-f", "--func", help=t(
        "function filter; gnl: any BUFFER_SIZE list (1,42,77,100k,def)",
        "filtre de fonctions ; gnl : n'importe quels BUFFER_SIZE (1,42,77,100k,def)"))
    result.add_argument("--checker", metavar="PATH", help=t(
        "push_swap: official checker_linux used to confirm the sorts (default: project folder, then ~/Downloads)",
        "push_swap : checker_linux officiel qui confirme les tris (défaut : dossier du projet, puis ~/Downloads)"))
    result.add_argument("--file", dest="files", action="append", default=[], metavar="FILE|SIZE", help=t(
        "gnl: test only your own file, or a generated file of that size (64k, 2M); repeatable, comma-separated",
        "gnl : tester seulement ton fichier, ou un fichier généré de cette taille (64k, 2M) ; répétable, séparé par des virgules"))
    result.add_argument("-p", "--part", type=positive, help=t("test only part N", "tester seulement la partie N"))
    result.add_argument("--seed", type=unsigned, default=42, help=t("random seed (default: 42)", "graine aléatoire (défaut : 42)"))
    result.add_argument("--timeout", type=positive, help=t("seconds per C test", "secondes par test C"))
    result.add_argument("-c", "--chill", action="store_true", help=t(
        "downgrade style/hygiene check KOs to warnings",
        "passer les vérifications style/hygiène KO en avertissements"))
    result.add_argument("--no-checks", action="store_true", help=t("skip subject checks", "ignorer les vérifications du sujet"))
    result.add_argument("--no-norm", action="store_true", help=t("skip norminette (or flake8/mypy)", "ignorer norminette (ou flake8/mypy)"))
    result.add_argument("--no-sanitize", action="store_true", help=t(
        "skip the -fsanitize=address,undefined pass", "sauter la passe -fsanitize=address,undefined"))
    result.add_argument("--no-valgrind", action="store_true", help=t(
        "skip the valgrind (memcheck) pass", "sauter la passe valgrind (memcheck)"))
    result.add_argument("--no-hidden", action="store_true", help=t("ignore hidden files and folders", "ignorer les fichiers et dossiers cachés"))
    result.add_argument("--no-color", action="store_true", help=t("disable colors", "désactiver les couleurs"))
    result.add_argument("--repro", metavar="TEST", help=t(
        "rebuild one failing test alone with your code and run it under valgrind (TEST is printed by -v)",
        "recompiler un test qui échoue seul avec ton code et le lancer sous valgrind (TEST est donné par -v)"))
    result.add_argument("--gdb", action="store_true", help=t(
        "with --repro: run the test under gdb", "avec --repro : lancer le test sous gdb"))
    return result


@contextmanager
def run_lock(root: Path):
    # C logs, statistics, and check probes share checkout paths.
    # Prevent two Python runs corrupting those files rather than racing silently.
    (root / "build").mkdir(exist_ok=True)
    with (root / "build/.runner.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RunnerError("Another Python ftorture run is using this checkout.") from exc
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def execute(ctx: Context, project: Project) -> int:
    if platform.system() != "Linux":
        raise RunnerError(ctx.message("This runner requires Linux.", "Ce lanceur exige Linux."))
    project.validate(ctx)
    tools = (*(ctx.cc[:1] if project.requires_compiler else ()), *project.tools,
             *(project.check_tools if ctx.options.checks else ()))
    for tool in tools:
        if not shutil.which(tool):
            raise RunnerError(ctx.message("Missing dependency:", "Dépendance absente :") + f" {tool}")
    with run_lock(ctx.root):
        ctx.build.mkdir(parents=True, exist_ok=True)
        ctx.stats.unlink(missing_ok=True)
        completed = False
        try:
            run_header(project, ctx.options)
            if ctx.options.repro:
                from .repro import run as run_repro
                return run_repro(ctx, project)
            # valgrind and the sanitizers start now, during the checks and tests
            if hasattr(project, "prestart"):
                project.prestart(ctx)
            if ctx.options.checks:
                project.checks(ctx)
            status = project.run(ctx)
            completed = True
            return status
        finally:
            ctx.stop_background()
            project.cleanup(ctx)
            if completed:
                run_footer(ctx.options)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    language = argparse.ArgumentParser(add_help=False)
    language.add_argument("--lang", choices=("en", "fr"), default=default_language())
    lang = language.parse_known_args(argv)[0].lang
    cli = parser(lang)
    args = cli.parse_intermixed_args(normalize_efficiency_args(argv))
    old_term = signal.getsignal(signal.SIGTERM)

    def interrupt(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupt)
    try:
        registry = load_registry(args.custom_tests_dir)
        if args.list_projects:
            for project in registry.projects:
                label = " [CUSTOM]" if project.custom else ""
                print(f"{project.key:10} {project.name:16} {project.subject}{label}")
            return 0
        project = registry.find(args.target)
        if project is not None:
            directory = Path(args.directory or ".").expanduser().resolve()
        elif args.directory:
            cli.error("expected a project name before the directory")
        else:
            directory = Path(args.target or ".").expanduser().resolve()
        if not directory.is_dir():
            raise RunnerError(f"{directory}: " + text(lang, "directory not found", "dossier introuvable"))
        options = Options(directory=directory, lang=lang, checks=not args.no_checks, chill=args.chill,
                          norm=not args.no_norm, speculative=args.speculative, verbose=args.verbose,
                          efficiency=args.efficiency or args.efficiency_target is not None,
                          efficiency_target=50 if args.efficiency_target is None else args.efficiency_target,
                          seed=args.seed, part=args.part, functions=args.func, timeout=args.timeout,
                          no_color=args.no_color, ignore_hidden=args.no_hidden,
                          files=tuple(item for value in args.files for item in value.split(",") if item.strip()),
                          checker=args.checker,
                          sanitize=not args.no_sanitize,
                          valgrind=not args.no_valgrind,
                          repro=args.repro, gdb=args.gdb)
        if args.gdb and not args.repro:
            cli.error("--gdb needs --repro")
        if args.target is None and sys.stdin.isatty() and sys.stdout.isatty():
            project, options = interactive(options, registry)
        else:
            project = project or registry.detect(directory)
        if project is None:
            raise RunnerError(text(lang, "No supported project found.", "Aucun projet reconnu dans ce dossier."))
        if options.files and project.key != "gnl":
            raise RunnerError(text(lang, "--file is for get_next_line only.", "--file ne sert qu'à get_next_line."))
        return execute(Context(ROOT, project.key, options), project)
    except (RunnerError, OSError) as exc:
        print(f"ftorture: {exc}", file=sys.stderr)
        return 2
    except EOFError:
        return 0
    except KeyboardInterrupt:
        print(text(lang, "\nInterrupted.", "\nInterrompu."), file=sys.stderr)
        return 130
    finally:
        signal.signal(signal.SIGTERM, old_term)
