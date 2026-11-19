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
from .ui import interactive, run_header

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


def parser(lang: str) -> argparse.ArgumentParser:
    def t(en: str, fr: str) -> str:
        return text(lang, en, fr)
    result = argparse.ArgumentParser(prog="torture", description=t(
        "Test 42 projects with the ftorture C engine.", "Tester les projets 42 avec le moteur C ftorture."))
    result.add_argument("target", nargs="?", help=t("project name or directory", "nom du projet ou dossier"))
    result.add_argument("directory", nargs="?", help=t("project directory", "dossier du projet"))
    result.add_argument("--lang", choices=("en", "fr"), default=lang, help=t("output language", "langue"))
    result.add_argument("--list-projects", action="store_true", help=t("list supported projects", "lister les projets"))
    result.add_argument("--custom-tests-dir", type=Path, help=t("directory of user test manifests", "dossier des tests personnalisés"))
    result.add_argument("-s", "--speculative", action="store_true", help=t("count ▲ as failures", "compter les ▲ comme erreurs"))
    result.add_argument("-v", "--verbose", action="store_true", help=t("show all failure details", "afficher tous les détails"))
    result.add_argument("-f", "--func", help=t("function or BUFFER_SIZE filter", "filtre fonction ou BUFFER_SIZE"))
    result.add_argument("-p", "--part", type=positive, help=t("test only part N", "tester seulement la partie N"))
    result.add_argument("--seed", type=unsigned, default=42, help=t("random seed (default: 42)", "graine aléatoire (défaut : 42)"))
    result.add_argument("--timeout", type=positive, help=t("seconds per C test", "secondes par test C"))
    result.add_argument("--no-checks", action="store_true", help=t("skip subject checks", "ignorer les vérifications du sujet"))
    result.add_argument("--no-norm", action="store_true", help=t("skip norminette", "ignorer norminette"))
    result.add_argument("--no-hidden", action="store_true", help=t("ignore hidden files and folders", "ignorer les fichiers et dossiers cachés"))
    result.add_argument("--no-color", action="store_true", help=t("disable colors", "désactiver les couleurs"))
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
        try:
            run_header(project, ctx.options)
            if ctx.options.checks:
                project.checks(ctx)
            return project.run(ctx)
        finally:
            project.cleanup(ctx)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    language = argparse.ArgumentParser(add_help=False)
    language.add_argument("--lang", choices=("en", "fr"), default=default_language())
    lang = language.parse_known_args(argv)[0].lang
    cli = parser(lang)
    args = cli.parse_intermixed_args(argv)
    old_term = signal.getsignal(signal.SIGTERM)

    def interrupt(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupt)
    try:
        registry = load_registry(args.custom_tests_dir)
        if args.list_projects:
            for project in registry.projects:
                label = " [CUSTOM]" if project.custom else ""
                print(f"{project.key:8} {project.name:16} {project.subject}{label}")
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
        options = Options(directory=directory, lang=lang, checks=not args.no_checks,
                          norm=not args.no_norm, speculative=args.speculative, verbose=args.verbose,
                          seed=args.seed, part=args.part, functions=args.func, timeout=args.timeout,
                          no_color=args.no_color, ignore_hidden=args.no_hidden)
        if args.target is None and sys.stdin.isatty() and sys.stdout.isatty():
            project, options = interactive(options, registry)
        else:
            project = project or registry.detect(directory)
        if project is None:
            raise RunnerError(text(lang, "No supported project header found.", "Aucun en-tête de projet reconnu."))
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
