"""Declarative user test suites. Discovery reads data; execution is explicit."""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import string
import sys

from .base import Project
from ..runtime import Context, RunnerError

FIELDS = {"directory", "build", "root", "tests_dir", "python", "seed"}


@dataclass(frozen=True)
class Case:
    name: str
    command: tuple[str, ...]
    part: int = 1
    expected_exit: int = 0
    speculative: bool = False


@dataclass(frozen=True)
class CustomProject(Project):
    custom: bool = True
    requires_compiler: bool = False
    tools: tuple[str, ...] = ()
    manifest: Path = Path()
    cases: tuple[Case, ...] = ()
    build_commands: tuple[tuple[str, ...], ...] = ()
    cleanup_commands: tuple[tuple[str, ...], ...] = ()
    timeout: int = 3

    def validate(self, ctx: Context) -> None:
        if self.header and not (ctx.options.directory / self.header).is_file():
            raise RunnerError(f"Missing custom project header: {self.header}")
        if ctx.options.part is not None and ctx.options.part not in self.parts:
            raise RunnerError(f"Invalid custom test part: {ctx.options.part}")
        self.selected(ctx)

    def selected(self, ctx: Context) -> tuple[Case, ...]:
        names = set(ctx.options.functions.split(",")) if ctx.options.functions else None
        if names is not None and (unknown := names - {case.name for case in self.cases}):
            raise RunnerError("Unknown custom test: " + ", ".join(sorted(unknown)))
        cases = tuple(case for case in self.cases
                      if (names is None or case.name in names)
                      and (ctx.options.part is None or case.part == ctx.options.part))
        if not cases:
            raise RunnerError("No custom tests selected")
        return cases

    def expand(self, command: tuple[str, ...], ctx: Context) -> list[str]:
        values = {"directory": str(ctx.options.directory), "build": str(ctx.build),
                  "root": str(ctx.root), "tests_dir": str(self.manifest.parent),
                  "python": sys.executable, "seed": str(ctx.options.seed)}
        return [arg.format_map(values) for arg in command]

    def environment(self, ctx: Context) -> dict[str, str]:
        return {**ctx.env, "FTORTURE_DIRECTORY": str(ctx.options.directory),
                "FTORTURE_BUILD": str(ctx.build), "FTORTURE_TESTS_DIR": str(self.manifest.parent),
                "FTORTURE_SEED": str(ctx.options.seed), "FTORTURE_PROJECT": self.key}

    def checks(self, ctx: Context) -> None:
        print(ctx.message("   [CUSTOM] Subject checks: not applicable (user-owned suite).",
                          "   [CUSTOM] Vérifications du sujet : non applicables (tests personnels)."), flush=True)

    def run(self, ctx: Context) -> int:
        from ..ui import Terminal
        terminal = Terminal(ctx.options.lang, ctx.options.no_color)
        report = ctx.root / "ftorture.log"
        report.write_text(f"[CUSTOM] {self.name}\nManifest: {self.manifest}\n", encoding="utf-8")
        for index, command in enumerate(self.build_commands, 1):
            log = ctx.build / f"build-{index}.log"
            if ctx.command(self.expand(command, ctx), cwd=ctx.build, log=log, env=self.environment(ctx)):
                raise RunnerError(f"Custom build failed; see {log}")
        passed = failed = speculative = 0
        for index, case in enumerate(self.selected(ctx), 1):
            log = ctx.build / f"test-{index}.log"
            status = ctx.command(self.expand(case.command, ctx), cwd=ctx.build, log=log,
                                 env=self.environment(ctx), timeout=ctx.options.timeout or self.timeout)
            ok = status == case.expected_exit and status != 124
            if ok:
                passed += 1
            elif case.speculative:
                speculative += 1
            else:
                failed += 1
            mark = "✔" if ok else "▲" if case.speculative else "T" if status == 124 else "✘"
            color = terminal.ph if ok else terminal.escape("38;5;221") if case.speculative else terminal.red
            terminal.write(f"   {color}{mark}{terminal.reset} [CUSTOM] {case.name}\n")
            output = log.read_text(errors="replace")
            with report.open("a", encoding="utf-8") as stream:
                stream.write(f"\n[{mark}] {case.name}: expected exit {case.expected_exit}, actual {status}\n")
                stream.write(re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", output))
            if not ok:
                terminal.write(f"       {ctx.message('Details:', 'Détails :')} {log}\n")
            if ctx.options.verbose:
                terminal.write("".join("       " + line + "\n" for line in output.splitlines()))
        bad = failed + (speculative if ctx.options.speculative else 0)
        summary = f"[CUSTOM] {passed} OK · {failed} KO · {speculative} ▲"
        terminal.write(f"\n   {terminal.inverse} {ctx.message('RESULT', 'RÉSULTAT')} {terminal.reset} {summary}\n\n")
        with report.open("a", encoding="utf-8") as stream:
            stream.write(f"\nTOTAL: {summary} -> {'KO' if bad else 'OK'}\n")
        return int(bool(bad))

    def cleanup(self, ctx: Context) -> None:
        for index, command in enumerate(self.cleanup_commands, 1):
            log = ctx.build / f"cleanup-{index}.log"
            if ctx.command(self.expand(command, ctx), cwd=ctx.build, log=log, env=self.environment(ctx)):
                raise RunnerError(f"Custom cleanup failed; see {log}")


def command(value) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or any(not isinstance(arg, str) or not arg or "\0" in arg for arg in value):
        raise ValueError("commands must be nonempty arrays of nonempty strings")
    for arg in value:
        for _, field, specification, conversion in string.Formatter().parse(arg):
            if field is not None and (field not in FIELDS or specification or conversion):
                raise ValueError(f"unsupported command placeholder: {field}")
    return tuple(value)


def integer(value, name: str, low=1, high=0x7FFFFFFF) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer between {low} and {high}")
    return value


def load(path: Path) -> CustomProject:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        allowed = {"version", "key", "name", "header", "timeout", "build", "cleanup", "tests"}
        if not isinstance(data, dict) or data.keys() - allowed:
            raise ValueError("manifest must be an object with documented fields only")
        if type(data.get("version")) is not int or data["version"] != 1:
            raise ValueError("manifest version must be 1")
        key = data.get("key")
        if not isinstance(key, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,47}", key):
            raise ValueError("key must use lowercase letters, digits and hyphens")
        name = data.get("name")
        if not isinstance(name, str) or not name.strip() or not name.isprintable():
            raise ValueError("name must be a nonempty printable string")
        header = data.get("header", "")
        if not isinstance(header, str) or (header and (not header.isprintable() or Path(header).is_absolute() or ".." in Path(header).parts)):
            raise ValueError("header must be a relative path inside the project")
        tests = data.get("tests")
        if not isinstance(tests, list) or not tests:
            raise ValueError("tests must be a nonempty array")
        cases = []
        names = set()
        for test in tests:
            if not isinstance(test, dict) or test.keys() - {"name", "command", "part", "expected_exit", "speculative"}:
                raise ValueError("test must be an object with documented fields only")
            label = test.get("name")
            if not isinstance(label, str) or not label or not label.isprintable() or "," in label or label in names:
                raise ValueError("test names must be unique printable strings without commas")
            names.add(label)
            spec = test.get("speculative", False)
            if type(spec) is not bool:
                raise ValueError("speculative must be a boolean")
            cases.append(Case(label, command(test.get("command")),
                              integer(test.get("part", 1), "part", high=3),
                              integer(test.get("expected_exit", 0), "expected_exit", low=0, high=255), spec))
        steps = []
        for field in ("build", "cleanup"):
            value = data.get(field, [])
            if not isinstance(value, list):
                raise ValueError(f"{field} must be an array of command arrays")
            steps.append(tuple(command(step) for step in value))
        return CustomProject(key=f"custom-{key}", name=name, header=header, subject="custom v1",
                             parts=tuple(sorted({case.part for case in cases})), manifest=path.resolve(),
                             cases=tuple(cases), build_commands=steps[0], cleanup_commands=steps[1],
                             timeout=integer(data.get("timeout", 3), "timeout"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise RunnerError(f"Invalid custom manifest {path}: {exc}") from exc


def discover(directory: Path | None = None) -> tuple[CustomProject, ...]:
    if directory is None:
        directory = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "ftorture/tests"
    directory = directory.expanduser()
    if not directory.exists():
        return ()
    if not directory.is_dir():
        raise RunnerError(f"Custom test directory is not a directory: {directory}")
    return tuple(load(path) for path in sorted(directory.glob("*.json")))
