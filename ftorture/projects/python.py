"""Reusable isolated Python test runner for 42 Python projects."""
from collections.abc import Callable
from dataclasses import dataclass
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

from .base import Project
from ..runtime import Context, RunnerError
from ..subject.python import ExerciseSpec, python_checks


@dataclass(frozen=True)
class PyOutcome:
    ok: bool
    detail: str = ""
    input_desc: str = ""
    expected: str = ""
    actual: str = ""
    timed_out: bool = False


@dataclass(frozen=True)
class PyTestCase:
    name_en: str
    name_fr: str
    runner: Callable[[Context, Path, int], PyOutcome]
    speculative: bool = False
    timeout: int | None = None


@dataclass(frozen=True)
class PySuite:
    key: str
    label: str
    files: tuple[str, ...]
    cases: tuple[PyTestCase, ...]
    aliases: tuple[str, ...] = ()
    part: int = 1


def run_python_subprocess(ctx: Context, args: list[str], *, cwd: Path,
                          stdin: str | None = None, timeout: int = 5,
                          extra_env: dict[str, str] | None = None) -> tuple[int, str, str]:
    """Run a Python child in its own process group without writing __pycache__."""
    env = {**ctx.env, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"}
    if extra_env:
        env.update(extra_env)
    with subprocess.Popen(
        args, cwd=cwd, env=env,
        stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        start_new_session=True,
    ) as proc:
        try:
            out, err = proc.communicate(None if stdin is None else stdin.encode("utf-8"), timeout=timeout)
            return proc.returncode, out.decode("utf-8", errors="replace"), err.decode("utf-8", errors="replace")
        except (KeyboardInterrupt, subprocess.TimeoutExpired) as exc:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                pass
            finally:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait()
            if isinstance(exc, KeyboardInterrupt):
                raise
            return 124, "", f"Timed out after {timeout}s"


def eval_module_code(ctx: Context, directory: Path, rel_path: str, code: str, *,
                     stdin: str | None = None, timeout: int = 5) -> tuple[int, str, str]:
    """Load student's `rel_path` via importlib and execute `code` with `mod` bound."""
    file_path = directory / rel_path
    harness = (
        "import importlib.util, io, sys, contextlib\n"
        f"_path = {str(file_path)!r}\n"
        "_spec = importlib.util.spec_from_file_location('_student_mod', _path)\n"
        "_mod = importlib.util.module_from_spec(_spec)\n"
        "_spec.loader.exec_module(_mod)\n"
        "mod = _mod\n"
        + code
    )
    return run_python_subprocess(
        ctx, [sys.executable, "-c", harness],
        cwd=file_path.parent, stdin=stdin, timeout=timeout,
    )


def run_script_file(ctx: Context, directory: Path, rel_path: str, *,
                    stdin: str | None = None, timeout: int = 5) -> tuple[int, str, str]:
    """Execute a student Python file directly as `python3 <file>`."""
    file_path = directory / rel_path
    return run_python_subprocess(
        ctx, [sys.executable, str(file_path)],
        cwd=file_path.parent, stdin=stdin, timeout=timeout,
    )


@dataclass(frozen=True)
class PythonProject(Project):
    requires_compiler: bool = False
    requires_makefile: bool = False
    tools: tuple[str, ...] = ()
    nested: bool = False
    parts: tuple[int, ...] = (1,)
    specs: tuple[ExerciseSpec, ...] = ()
    suites: tuple[PySuite, ...] = ()
    check_naming_conventions: bool = False
    default_timeout: int = 5

    @property
    def markers(self) -> tuple[str, ...]:
        return tuple(rel for spec in self.specs for rel in spec.relative_files)

    def matches(self, directory: Path, *, ignore_hidden: bool = False) -> bool:
        return any((directory / rel).is_file() for rel in self.markers)

    def validate(self, ctx: Context) -> None:
        directory = ctx.options.directory
        has_marker = self.matches(directory)
        has_ex_dir = any((directory / spec.directory).is_dir() for spec in self.specs if spec.directory)
        if not has_marker and not has_ex_dir:
            raise RunnerError(
                f"{directory}: " + ctx.message(
                    f"no {self.name} exercise files found",
                    f"aucun fichier d'exercice {self.name} trouvé",
                )
            )
        if ctx.options.part is not None and ctx.options.part not in self.parts:
            raise RunnerError(ctx.message("Invalid part for", "Partie invalide pour") + f" {self.name}")
        self.selected_suites(ctx)

    def selected_suites(self, ctx: Context) -> tuple[PySuite, ...]:
        part = ctx.options.part
        suites = tuple(s for s in self.suites if part is None or s.part == part)
        if ctx.options.functions:
            wanted = [item.strip().lower() for item in ctx.options.functions.split(",") if item.strip()]
            chosen = []
            unknown = []
            for token in wanted:
                matched = [
                    s for s in suites
                    if token == s.key.lower()
                    or token in {a.lower() for a in s.aliases}
                    or any(token == Path(f).stem.lower() or token == Path(f).name.lower() for f in s.files)
                ]
                if not matched:
                    unknown.append(token)
                else:
                    for s in matched:
                        if s not in chosen:
                            chosen.append(s)
            if unknown:
                raise RunnerError(
                    ctx.message("Unknown exercise/filter: ", "Exercice/filtre inconnu : ") + ", ".join(unknown)
                )
            suites = tuple(chosen)
        if not suites:
            raise RunnerError(ctx.message("No exercises selected", "Aucun exercice sélectionné"))
        return suites

    def checks(self, ctx: Context) -> None:
        python_checks(ctx, self.specs, check_naming_conventions=self.check_naming_conventions)

    def run(self, ctx: Context) -> int:
        renderer = ctx.renderer
        renderer.log_lines.extend([f"{self.name} (subject v{self.subject})", f"Path: {ctx.options.directory}"])
        if ctx.options.checks:
            renderer.render_checks(ctx.checks_file)
        renderer.render_legend(c_mode=False)
        renderer.render_part(
            1,
            ctx.message("PART 1 · Exercises", "PARTIE 1 · Exercices"),
            ctx.message("exercises", "exercices"),
        )
        directory = ctx.options.directory
        base_timeout = ctx.options.timeout or self.default_timeout

        for suite in self.selected_suites(ctx):
            missing = [rel for rel in suite.files if not (directory / rel).is_file()]
            if missing:
                msg = ctx.message("missing: ", "absent : ") + ", ".join(missing)
                renderer.record_suite(part=suite.part, short_name=ctx.message("exercises", "exercices"),
                                      label=suite.label, outcomes=[], missing_msg=msg)
                continue
            outcomes = []
            for case in suite.cases:
                timeout = ctx.options.timeout or case.timeout or base_timeout
                outcome = case.runner(ctx, directory, timeout)
                sym = "✔" if outcome.ok else ("▲" if case.speculative else ("T" if outcome.timed_out else "✘"))
                outcomes.append((sym, ctx.message(case.name_en, case.name_fr), outcome.detail,
                                 case.speculative, outcome.input_desc, outcome.expected, outcome.actual))
            renderer.record_suite(part=suite.part, short_name=ctx.message("exercises", "exercices"),
                                  label=suite.label, outcomes=outcomes)

        return renderer.finish(item_en="exercises", item_fr="exercices")


def expect_json_outcome(ctx: Context, directory: Path, rel_path: str, code: str, *,
                        stdin: str | None = None, timeout: int = 5,
                        input_desc: str = "") -> PyOutcome:
    """Run `code` which prints a JSON dict {ok, detail, expected, actual} on the last line."""
    status, stdout, stderr = eval_module_code(ctx, directory, rel_path, code, stdin=stdin, timeout=timeout)
    if status == 124:
        return PyOutcome(False, f"timeout ({timeout}s)", input_desc=input_desc, timed_out=True)
    if status != 0:
        err = (stderr.strip() or stdout.strip()).splitlines()
        summary = err[-1] if err else f"exit code {status}"
        return PyOutcome(False, summary, input_desc=input_desc, actual="\n".join(err[-4:]))
    lines = [line for line in stdout.splitlines() if line.strip()]
    if not lines:
        return PyOutcome(False, "no test output", input_desc=input_desc)
    try:
        payload = json.loads(lines[-1])
        return PyOutcome(
            bool(payload.get("ok")),
            str(payload.get("detail", "")),
            input_desc=input_desc or str(payload.get("input", "")),
            expected=str(payload.get("expected", "")),
            actual=str(payload.get("actual", "")),
        )
    except (ValueError, TypeError):
        return PyOutcome(False, "unexpected harness output", input_desc=input_desc, actual=stdout.strip())
