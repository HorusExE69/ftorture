"""Shared subprocess, artifact, and C-engine interfaces."""
from dataclasses import dataclass, field
from contextlib import nullcontext
import json
from pathlib import Path
import os
import shlex
import signal
import subprocess
import threading
from concurrent.futures import TimeoutError
import sys

from .language import text


_COUNTERS = threading.Lock()


class RunnerError(Exception):
    """An operational failure, not a failing student test."""


@dataclass(frozen=True)
class Options:
    directory: Path
    lang: str = "en"
    checks: bool = True
    chill: bool = False
    norm: bool = True
    speculative: bool = False
    verbose: bool = False
    efficiency: bool = False
    efficiency_target: int = 50
    seed: int = 42
    part: int | None = None
    functions: str | None = None
    timeout: int | None = None
    no_color: bool = False
    ignore_hidden: bool = False
    sanitize: bool = True           # -fsanitize=address,undefined pass (--no-sanitize)
    valgrind: bool = True           # memcheck pass on the same tests (--no-valgrind)
    files: tuple[str, ...] = ()     # gnl --file: paths or sizes (normalized by the project)
    checker: str | None = None      # push_swap --checker: the official checker_linux
    repro: str | None = None        # --repro FILE#IDX[mK][@SUITE[=BS]]: rebuild one test alone
    gdb: bool = False               # --repro under gdb instead of valgrind


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
                timeout: int | None = None, stdin: str | None = None) -> int:
        command = [str(arg) for arg in args]
        # only the main thread draws the "▶ cc…" line (workers run in parallel)
        progress = (log is not None and sys.stdout.isatty()
                    and threading.current_thread() is threading.main_thread())
        if progress:
            color = not self.env.get("NO_COLOR")
            label = Path(command[0]).name
            green, dim, reset = ("\033[38;5;46m", "\033[38;5;34m", "\033[0m") if color else ("", "", "")
            print(f"\r\033[K   {green}▶{reset} {dim}{label}…{reset}", end="", flush=True)
        try:
            return self._command(command, cwd=cwd, log=log, env=env, timeout=timeout, stdin=stdin)
        finally:
            if progress:
                print("\r\033[K", end="", flush=True)

    def _command(self, command: list[str], *, cwd: Path | None,
                 log: Path | None, env: dict[str, str] | None, timeout: int | None,
                 stdin: str | None = None) -> int:
        with log.open("w") if log else nullcontext(None) as output:
            # A private session lets cancellation stop make/compiler/test children
            # before cleanup touches the student's build artifacts.
            with subprocess.Popen(command, cwd=cwd, env=self.env if env is None else env, stdout=output,
                                  stderr=subprocess.STDOUT if log else None,
                                  stdin=None if stdin is None else subprocess.PIPE,
                                  start_new_session=True) as process:
                try:
                    if stdin is not None:
                        process.communicate(stdin.encode(), timeout=timeout)
                        return process.returncode
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

    def cached_object(self, source: Path, flags: list[str | Path], log: Path) -> Path | None:
        """`cc <flags> -c source` through build/cache: reused while the source,
        the flags, the compiler and every header of its -I folders (and of its
        own folder) are unchanged. None if it does not compile (see log)."""
        import hashlib
        digest = hashlib.sha256()
        digest.update("\0".join(map(str, [*self.cc, *flags, source])).encode())
        digest.update(Path(source).read_bytes())
        folders = {Path(source).parent} | {Path(str(f)[2:]) for f in flags if str(f).startswith("-I")}
        for folder in sorted(folders):
            for header in sorted(folder.glob("*.h")) if folder.is_dir() else ():
                digest.update(str(header).encode())
                digest.update(header.read_bytes())
        cache = self.root / "build" / "cache"
        cache.mkdir(parents=True, exist_ok=True)
        target = cache / f"{digest.hexdigest()[:32]}.o"
        if target.is_file():
            return target
        temporary = cache / f"{target.stem}.{os.getpid()}.{threading.get_ident()}.tmp.o"
        if self.command([*self.cc, *flags, "-c", source, "-o", temporary], log=log):
            temporary.unlink(missing_ok=True)
            return None
        os.replace(temporary, target)
        return target

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
        if opts.efficiency:
            args.extend(["-e", str(opts.efficiency_target)])
        if opts.no_color:
            args.append("--no-color")
        if opts.timeout:
            args.extend(["--timeout", str(opts.timeout)])
        if function_filter and opts.functions:
            args.extend(["-f", opts.functions])
        # -v prints "torture <key> <dir> --repro TOKEN" under each failure
        args.extend(["--repro-cmd", self.repro_prefix()])
        return args

    def repro_prefix(self) -> str:
        prefix = ["torture", self.key, str(self.options.directory)]
        if self.options.lang == "en":
            prefix.extend(["--lang", "en"])
        if self.options.seed != 42:
            prefix.extend(["--seed", str(self.options.seed)])
        return shlex.join(prefix)

    @property
    def renderer(self):
        if not hasattr(self, "_renderer"):
            from .renderer import Renderer
            self._renderer = Renderer(self.options, self.root / "ftorture.log", repro_prefix=self.repro_prefix())
        return self._renderer

    # ---- background work (valgrind, sanitizers) -----------------------------
    @property
    def slow(self) -> dict:
        """Futures of the passes started early, by (kind, rule)."""
        if not hasattr(self, "_slow"):
            self._slow = {}
        return self._slow

    def background(self, fn, *args):
        if not hasattr(self, "_pool"):
            from concurrent.futures import ThreadPoolExecutor
            self._pool = ThreadPoolExecutor(4)
        return self._pool.submit(fn, *args)

    def shard_started(self, count: int) -> None:
        with _COUNTERS:
            self._shards = getattr(self, "_shards", 0) + count

    def shard_done(self) -> None:
        with _COUNTERS:
            self._shards_done = getattr(self, "_shards_done", 0) + 1

    def wait(self, future):
        """future.result(), with a live "▶ valgrind + sanitizers… 5/16" line."""
        tty = sys.stdout.isatty()
        while True:
            try:
                return future.result(timeout=0.2)
            except TimeoutError:
                if tty:
                    done, total = getattr(self, "_shards_done", 0), getattr(self, "_shards", 0)
                    label = self.message("valgrind + sanitizers", "valgrind + sanitizers")
                    print(f"\r\033[K   ▶ {label}… {done}/{total}", end="", flush=True)
            finally:
                if tty and future.done():
                    print("\r\033[K", end="", flush=True)

    def stop_background(self) -> None:
        self.kill_children()
        if hasattr(self, "_pool"):
            self._pool.shutdown(wait=False, cancel_futures=True)

    # ---- parallel runs: capture now, display later in order ------------------
    def track(self, process: subprocess.Popen) -> None:
        """Remember a child started by a worker thread, so Ctrl-C stops it."""
        if not hasattr(self, "_children"):
            self._children = []
        self._children.append(process)

    def kill_children(self) -> None:
        for process in getattr(self, "_children", []):
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        for process in getattr(self, "_children", []):
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass

    def capture_tester(self, executable: Path, extra: list[str | Path], *,
                       function_filter: bool = True) -> tuple[int, list[str]]:
        """Run a tester without displaying it (thread-safe): (status, its lines)."""
        command = [str(arg) for arg in (executable, *self.engine_args(function_filter=function_filter), *extra)]
        process = subprocess.Popen(command, cwd=self.build, env=self.env, stdout=subprocess.PIPE,
                                   start_new_session=True)
        self.track(process)
        out, _ = process.communicate()
        status = process.returncode
        return (128 - status if status < 0 else status), out.decode("utf-8", errors="replace").splitlines()

    def replay_tester(self, lines: list[str], *, checks: bool = False) -> None:
        """Display the lines of a captured tester, as stream_tester would have."""
        if checks and self.options.checks:
            self.renderer.render_checks(self.checks_file)
        for line in lines:
            self._tester_line(line)

    def _tester_line(self, line: str) -> None:
        line = line.rstrip("\r\n")
        if not line:
            return
        if line.startswith("{"):
            try:
                self.renderer.consume_c_event(json.loads(line))
                return
            except ValueError:
                pass
        print(line, flush=True)

    def stream_tester(self, executable: Path, extra: list[str | Path], *,
                      checks: bool = False, function_filter: bool = True) -> int:
        if checks and self.options.checks:
            self.renderer.render_checks(self.checks_file)
        command = [str(arg) for arg in (executable, *self.engine_args(function_filter=function_filter), *extra)]
        with subprocess.Popen(command, cwd=self.build, env=self.env,
                              stdout=subprocess.PIPE, start_new_session=True) as process:
            try:
                assert process.stdout is not None
                for raw in process.stdout:
                    line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                    if not line:
                        continue
                    if line.startswith("{"):
                        try:
                            self.renderer.consume_c_event(json.loads(line))
                            continue
                        except ValueError:
                            pass
                    print(line, flush=True)
                status = process.wait()
                return 128 - status if status < 0 else status
            except KeyboardInterrupt:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
                finally:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait()
                raise

    def tester(self, executable: Path, extra: list[str | Path], *,
               checks: bool = False, function_filter: bool = True,
               note: str | None = None, item_en: str = "functions",
               item_fr: str = "fonctions", after=None) -> int:
        status = self.stream_tester(executable, extra, checks=checks, function_filter=function_filter)
        if status > 1:
            return status
        if after is not None:
            # e.g. the -fsanitize pass: its section comes before the summary
            records = after()
            for path in records if isinstance(records, list) else [records]:
                if path:
                    self.renderer.render_records(path)
        if note:
            self.renderer.add_note(note)
        return self.renderer.finish(item_en=item_en, item_fr=item_fr)
