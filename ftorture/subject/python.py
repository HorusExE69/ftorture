"""Native subject checks for 42 Python modules: structure, flake8, mypy, AST."""
import ast
import builtins
from dataclasses import dataclass
from pathlib import Path
import re
import shutil

from ..checks import CheckSession
from ..runtime import Context
from .common import check_files, project_files

BUILTIN_NAMES = frozenset(dir(builtins))
TYPE_IMPORTS = frozenset({"typing", "__future__", "collections.abc"})
PASCAL_RE = re.compile(r"^[A-Z][a-zA-Z0-9]*$")
SNAKE_RE = re.compile(r"^_?[a-z][a-z0-9_]*$")


@dataclass(frozen=True)
class ExerciseSpec:
    key: str
    directory: str
    files: tuple[str, ...]
    authorized: frozenset[str] = frozenset()
    allow_helpers: bool = False
    allow_classes: bool = False
    allow_main_block: bool = False
    require_main_block: bool = False
    require_type_hints: bool = False
    allowed_imports: frozenset[str] = frozenset()
    expected_functions: tuple[str, ...] = ()
    expected_classes: tuple[str, ...] = ()

    @property
    def relative_files(self) -> tuple[str, ...]:
        return tuple(f"{self.directory}/{name}" if self.directory else name for name in self.files)


def is_main_guard(node: ast.AST) -> bool:
    if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare):
        return False
    test = node.test
    if len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq) or len(test.comparators) != 1:
        return False
    left, right = test.left, test.comparators[0]
    pairs = ((left, right), (right, left))
    return any(isinstance(a, ast.Name) and a.id == "__name__"
               and isinstance(b, ast.Constant) and b.value == "__main__"
               for a, b in pairs)


def is_docstring(node: ast.AST) -> bool:
    return (isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str))


def allowed_python_path(expected_files: set[str], relative: str) -> bool:
    path = Path(relative)
    return path.name == ".gitignore" or relative in expected_files


def check_expected_files(session: CheckSession, specs: tuple[ExerciseSpec, ...]) -> list[str]:
    root = session.ctx.options.directory
    expected = [rel for spec in specs for rel in spec.relative_files]
    present = [rel for rel in expected if (root / rel).is_file()]
    missing = [rel for rel in expected if not (root / rel).is_file()]
    session.check(
        "KO" if missing else "OK",
        "Required files", "Fichiers attendus",
        f"{len(present)}/{len(expected)} present" + (f" ({len(missing)} missing)" if missing else ""),
        f"{len(present)}/{len(expected)} présents" + (f" ({len(missing)} manquants)" if missing else ""),
    )
    session.details(missing)
    return present


def check_syntax(session: CheckSession, files: list[str]) -> dict[str, ast.Module]:
    root = session.ctx.options.directory
    trees: dict[str, ast.Module] = {}
    errors: list[str] = []
    for rel in files:
        try:
            source = (root / rel).read_text(encoding="utf-8")
            trees[rel] = ast.parse(source, filename=rel)
        except (OSError, UnicodeError, SyntaxError) as exc:
            errors.append(f"{rel}: {exc}")
    session.check(
        "KO" if errors else "OK",
        "Python syntax", "Syntaxe Python",
        f"{len(errors)} syntax errors" if errors else f"{len(trees)} files parsed cleanly",
        f"{len(errors)} erreurs de syntaxe" if errors else f"{len(trees)} fichiers valides",
    )
    session.details(errors)
    return trees


def check_flake8(session: CheckSession, files: list[str]) -> None:
    if not session.ctx.options.norm:
        session.check("SKIP", "flake8", "flake8", "disabled (--no-norm)", "désactivé (--no-norm)")
        return
    if not shutil.which("flake8"):
        session.check("SKIP", "flake8", "flake8", "not installed (pip install flake8)",
                      "non installé (pip install flake8)")
        return
    if not files:
        session.check("SKIP", "flake8", "flake8", "no .py file", "aucun fichier .py")
        return
    status, output = session.capture(["flake8", *files], cwd=session.ctx.options.directory, name="flake8")
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    bad = bool(status or lines)
    session.check(
        "KO" if bad else "OK", "flake8", "flake8",
        f"{len(lines)} style issues; see checks/ logs" if bad else "no errors",
        f"{len(lines)} erreurs de style ; voir checks/" if bad else "aucune erreur",
        soft=True,
    )
    if bad:
        session.details(lines, 8)


def check_mypy(session: CheckSession, required_files: list[str], optional_files: list[str]) -> None:
    if not session.ctx.options.norm:
        session.check("SKIP", "mypy", "mypy", "disabled (--no-norm)", "désactivé (--no-norm)")
        return
    if not shutil.which("mypy"):
        session.check("SKIP", "mypy", "mypy", "not installed (pip install mypy)",
                      "non installé (pip install mypy)")
        return
    if not required_files and not optional_files:
        session.check("SKIP", "mypy", "mypy", "no .py file", "aucun fichier .py")
        return
    directory = session.ctx.options.directory
    cache_dir = str(session.directory / "mypy_cache")
    if required_files:
        status, output = session.capture(
            ["mypy", "--cache-dir", cache_dir, "--ignore-missing-imports", "--no-error-summary", *required_files],
            cwd=directory, name="mypy",
        )
        errors = [line.strip() for line in output.splitlines() if ": error:" in line]
        bad = bool(status or errors)
        session.check(
            "KO" if bad else "OK", "mypy (required)", "mypy (obligatoire)",
            f"{len(errors)} type errors; see checks/ logs" if bad else "no type errors",
            f"{len(errors)} erreurs de typage ; voir checks/" if bad else "aucune erreur de typage",
            soft=True,
        )
        if bad:
            session.details(errors or output.splitlines(), 8)
    if optional_files:
        status, output = session.capture(
            ["mypy", "--cache-dir", cache_dir, "--ignore-missing-imports", "--no-error-summary", *optional_files],
            cwd=directory, name="mypy-optional",
        )
        errors = [line.strip() for line in output.splitlines() if ": error:" in line]
        if status or errors:
            session.check(
                "WARN", "mypy (recommended)", "mypy (recommandé)",
                f"{len(errors)} issues in optional exercises",
                f"{len(errors)} remarques dans les exercices optionnels",
            )
            session.details(errors, 6)


def check_type_annotations(session: CheckSession, trees: dict[str, ast.Module],
                           required_files: list[str]) -> None:
    if not required_files:
        return
    missing: list[str] = []
    for rel in required_files:
        tree = trees.get(rel)
        if tree is None:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            args = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
            if node.args.vararg:
                args.append(node.args.vararg)
            if node.args.kwarg:
                args.append(node.args.kwarg)
            untyped = [arg.arg for arg in args if arg.arg not in ("self", "cls") and arg.annotation is None]
            if untyped:
                missing.append(f"{rel}:{node.lineno} {node.name}() untyped param(s): {', '.join(untyped)}")
            if node.returns is None:
                missing.append(f"{rel}:{node.lineno} {node.name}() missing return type")
    session.check(
        "KO" if missing else "OK",
        "Type annotations", "Annotations de type",
        f"{len(missing)} missing annotations" if missing else "all required signatures typed",
        f"{len(missing)} annotations manquantes" if missing else "toutes les signatures requises typées",
        soft=True,
    )
    session.details(missing, 8)


def check_top_level_policy(session: CheckSession, trees: dict[str, ast.Module],
                           specs: tuple[ExerciseSpec, ...]) -> None:
    issues: list[str] = []
    for spec in specs:
        for rel in spec.relative_files:
            tree = trees.get(rel)
            if tree is None:
                continue
            has_main = False
            for node in tree.body:
                if is_docstring(node):
                    continue
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    continue
                if isinstance(node, ast.ClassDef) and spec.allow_classes:
                    continue
                if is_main_guard(node):
                    has_main = True
                    if not spec.allow_main_block:
                        issues.append(f"{rel}:{node.lineno} forbidden if __name__ == '__main__' block")
                    continue
                if not spec.allow_main_block:
                    issues.append(f"{rel}:{node.lineno} top-level {type(node).__name__} outside functions")
            if spec.require_main_block and not has_main:
                issues.append(f"{rel}: missing if __name__ == '__main__' block")
    session.check(
        "KO" if issues else "OK",
        "Module structure", "Structure des modules",
        f"{len(issues)} structure violations" if issues else "clean module layout",
        f"{len(issues)} violations de structure" if issues else "structure conforme",
    )
    session.details(issues, 8)


def check_authorized(session: CheckSession, trees: dict[str, ast.Module],
                     specs: tuple[ExerciseSpec, ...]) -> None:
    issues: list[str] = []
    for spec in specs:
        allowed_imports = spec.allowed_imports | TYPE_IMPORTS
        for rel in spec.relative_files:
            tree = trees.get(rel)
            if tree is None:
                continue
            defined: set[str] = set()
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    defined.add(node.name)
                elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                    defined.add(node.id)
                elif isinstance(node, ast.arg):
                    defined.add(node.arg)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top = alias.name.split(".", 1)[0]
                        if alias.name not in allowed_imports and top not in allowed_imports:
                            issues.append(f"{rel}:{node.lineno} unauthorized import '{alias.name}'")
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    top = mod.split(".", 1)[0]
                    if mod not in allowed_imports and top not in allowed_imports:
                        issues.append(f"{rel}:{node.lineno} unauthorized import from '{mod}'")
                elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    name = node.func.id
                    if name in BUILTIN_NAMES and name not in defined and name not in spec.authorized:
                        issues.append(f"{rel}:{node.lineno} unauthorized builtin '{name}()'")
    session.check(
        "KO" if issues else "OK",
        "Authorized functions", "Fonctions autorisées",
        f"{len(issues)} unauthorized calls/imports" if issues else "only authorized builtins/imports",
        f"{len(issues)} appels/imports non autorisés" if issues else "uniquement les fonctions autorisées",
    )
    session.details(issues, 8)


def check_naming(session: CheckSession, trees: dict[str, ast.Module]) -> None:
    issues: list[str] = []
    for rel, tree in trees.items():
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and not PASCAL_RE.match(node.name):
                issues.append(f"{rel}:{node.lineno} class '{node.name}' should be PascalCase")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not (node.name.startswith("__") and node.name.endswith("__")) and not SNAKE_RE.match(node.name):
                    issues.append(f"{rel}:{node.lineno} function '{node.name}' should be snake_case")
    session.check(
        "KO" if issues else "OK",
        "Naming conventions", "Conventions de nommage",
        f"{len(issues)} naming issues" if issues else "PascalCase classes, snake_case functions",
        f"{len(issues)} erreurs de nommage" if issues else "classes en PascalCase, fonctions en snake_case",
        soft=True,
    )
    session.details(issues, 8)


def python_checks(ctx: Context, specs: tuple[ExerciseSpec, ...], *,
                  check_naming_conventions: bool = False) -> None:
    session = CheckSession(ctx)
    report = session.report
    expected_set = {rel for spec in specs for rel in spec.relative_files}
    try:
        report.section("STRUCTURE")
        check_files(session, lambda rel: allowed_python_path(expected_set, rel))
        present = check_expected_files(session, specs)
        # Also include any other non-ignored .py files for syntax/flake8 if present
        root = ctx.options.directory
        all_py = sorted({
            *present,
            *(p.relative_to(root).as_posix()
              for p in project_files(root, ignore_hidden=ctx.options.ignore_hidden)
              if p.suffix == ".py" and p.is_file() and not p.is_symlink()),
        })
        required_typed = [rel for spec in specs if spec.require_type_hints
                          for rel in spec.relative_files if rel in present]
        optional_typed = [rel for spec in specs if not spec.require_type_hints
                          for rel in spec.relative_files if rel in present]

        report.section(session.text("STYLE & TYPING", "STYLE & TYPAGE"))
        trees = check_syntax(session, all_py)
        check_flake8(session, present)
        check_mypy(session, required_typed, optional_typed)
        check_type_annotations(session, trees, required_typed)

        report.section("CODE")
        check_top_level_policy(session, trees, specs)
        check_authorized(session, trees, specs)
        if check_naming_conventions:
            check_naming(session, trees)
    finally:
        report.write(ctx.checks_file)
