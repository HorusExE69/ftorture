"""Shared subprocess, artifact, and C-engine interfaces."""
from dataclasses import dataclass, field
from contextlib import nullcontext
from pathlib import Path
import os
import shlex
import signal
import subprocess
import sys

from .language import text


class RunnerError(Exception):
    """An operational failure, not a failing student test."""


@dataclass(frozen=True)
class Options:
    directory: Path
    lang: str = "en"
    checks: bool = True
    norm: bool = True
    speculative: bool = False
    verbose: bool = False
    seed: int = 42
    part: int | None = None
    functions: str | None = None
    timeout: int | None = None
    no_color: bool = False
    ignore_hidden: bool = False


@dataclass
class Context:
    root: Path
    key: str
    options: Options
    env: dict[str, str] = field(default_factory=lambda: dict(os.environ))

    def __post_init__(self) -> None:
        self.env["FTORTURE_LANG"] = self.options.lang
        if self.options.no_color:
            self.env["NO_COLOR"] = "1"

    @property
    def build(self) -> Path:
        return self.root / "build" / self.key

    @property
    def checks_file(self) -> Path:
        return self.build / "checks.txt"

    @property
    def stats(self) -> Path:
        return self.build / "stats.bin"

    @property
    def cc(self) -> list[str]:
        # CC may contain an executable plus arguments (e.g. "ccache cc").
        try:
            command = shlex.split(self.env.get("CC", "cc"))
        except ValueError as exc:
            raise RunnerError(f"Invalid CC: {exc}") from exc
        if not command:
            raise RunnerError("CC is empty")
        return command

    def message(self, en: str, fr: str) -> str:
        return text(self.options.lang, en, fr)

    def command(self, args: list[str | Path], *, cwd: Path | None = None,
                log: Path | None = None, env: dict[str, str] | None = None,
                timeout: int | None = None) -> int:
        command = [str(arg) for arg in args]
        progress = log is not None and sys.stdout.isatty()
        if progress:
            color = not self.env.get("NO_COLOR")
            label = Path(command[0]).name
            green, dim, reset = ("\033[38;5;46m", "\033[38;5;34m", "\033[0m") if color else ("", "", "")
            print(f"\r\033[K   {green}▶{reset} {dim}{label}…{reset}", end="", flush=True)
        try:
            return self._command(command, cwd=cwd, log=log, env=env, timeout=timeout)
        finally:
            if progress:
                print("\r\033[K", end="", flush=True)

    def _command(self, command: list[str], *, cwd: Path | None,
                 log: Path | None, env: dict[str, str] | None, timeout: int | None) -> int:
        with log.open("w") if log else nullcontext(None) as output:
            # A private session lets cancellation stop make/compiler/test children
            # before cleanup touches the student's build artifacts.
            with subprocess.Popen(command, cwd=cwd, env=self.env if env is None else env, stdout=output,
                                  stderr=subprocess.STDOUT if log else None,
                                  start_new_session=True) as process:
                try:
                    return process.wait(timeout=timeout)
                except (KeyboardInterrupt, subprocess.TimeoutExpired) as exc:
                    try:
                        os.killpg(process.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        pass
                    finally:
                        # The parent may have stopped while a descendant ignored TERM.
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        process.wait()
                    if isinstance(exc, KeyboardInterrupt):
                        raise
                    return 124

    def compile(self, args: list[str | Path], log: Path) -> bool:
        return self.command([*self.cc, *args], log=log) == 0

    def require(self, args: list[str | Path], log: Path) -> None:
        if self.command(args, log=log):
            raise RunnerError(self.message("Command failed; see", "Échec ; voir") + f" {log}")

    def engine_flags(self, source_dir: str) -> list[str | Path]:
        return ["-std=gnu11", "-O0", "-g", "-w", "-fno-builtin",
                f"-I{self.root / 'src'}", f"-I{self.root / 'src' / source_dir}"]

    def engine_args(self, *, function_filter: bool = True) -> list[str | Path]:
        opts = self.options
        args: list[str | Path] = ["--no-banner", "--path", opts.directory, "--log", self.root / "ftorture.log",
                                  "--lang", opts.lang, "--seed", str(opts.seed)]
        if opts.speculative:
            args.append("-s")
        if opts.verbose:
            args.append("-v")
        if opts.no_color:
            args.append("--no-color")
        if opts.timeout:
            args.extend(["--timeout", str(opts.timeout)])
        if function_filter and opts.functions:
            args.extend(["-f", opts.functions])
        return args

    def tester(self, executable: Path, extra: list[str | Path], *,
               checks: bool = False, function_filter: bool = True) -> int:
        args = self.engine_args(function_filter=function_filter)
        if checks and self.options.checks:
            args.extend(["--checks", self.checks_file])
        status = self.command([executable, *args, *extra], cwd=self.build)
        return 128 - status if status < 0 else status
