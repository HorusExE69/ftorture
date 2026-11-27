"""-fsanitize pass: the student's C code built with AddressSanitizer and
UndefinedBehaviorSanitizer, the same tests run once more, silently, and every
report is turned into a SANITIZERS section (signed overflow such as `-n` on
INT_MIN, out-of-bounds stack/global/heap accesses, use after free, bad shifts…).

Test verdicts of this pass are ignored: only the sanitizer reports count. A
report in a speculative test (undefined input such as atoi overflow) is a ▲.
"""
from dataclasses import dataclass, field
from pathlib import Path
import os
import re
import shutil
import subprocess
import threading

from .checks import CheckReport
from .runtime import Context

SAN_FLAGS = ("-fsanitize=address,undefined", "-fno-sanitize=null,nonnull-attribute,returns-nonnull-attribute,pointer-overflow",
             "-fsanitize-recover=undefined", "-fno-omit-frame-pointer", "-g", "-O0")
LINK_FLAGS = ("-fsanitize=address,undefined",)


def available(ctx: Context) -> bool:
    """The compiler links an ASan + UBSan program (not every system has the runtimes)."""
    probe = ctx.build / "san-probe"
    probe.mkdir(parents=True, exist_ok=True)
    (probe / "p.c").write_text("int main(void){return 0;}\n")
    return ctx.command([*ctx.cc, *SAN_FLAGS, probe / "p.c", "-o", probe / "p"], log=probe / "probe.log") == 0


def environment(ctx: Context, directory: Path) -> dict[str, str]:
    env = dict(ctx.env)
    env["FTORTURE_SAN_DIR"] = str(directory)
    # Plain SEGVs stay crashes (the normal pass reports them); leaks are memtrack's job.
    env["ASAN_OPTIONS"] = ("detect_leaks=0:handle_segv=0:handle_sigbus=0:handle_abort=0:"
                           "allocator_may_return_null=1:detect_stack_use_after_return=0:"
                           "alloc_dealloc_mismatch=0:abort_on_error=0:print_summary=1")
    # UB does not stop the program: a test goes on, so its normal verdict tells
    # whether an overflow cancelled out (right result) or not.
    env["UBSAN_OPTIONS"] = "print_stacktrace=1:halt_on_error=0"
    return env


def compile_objects(ctx: Context, sources: list[Path], out: Path, *, defines: list[str] = (),
                    includes: list[Path] = (), flags: tuple[str, ...] = SAN_FLAGS) -> tuple[list[Path], str]:
    """Each source compiled with the sanitizers (or `flags`). Returns (objects, error log)."""
    from concurrent.futures import ThreadPoolExecutor
    out.mkdir(parents=True, exist_ok=True)
    options = [*flags, "-w", *defines, *(f"-I{d}" for d in includes)]
    logs = [out / f"{index:03d}-{source.stem}.log" for index, source in enumerate(sources)]
    # cached (build/cache) and in parallel: unchanged sources are not rebuilt
    with ThreadPoolExecutor(8) as pool:
        objects = list(pool.map(lambda pair: ctx.cached_object(pair[0], options, pair[1]), zip(sources, logs)))
    for obj, log in zip(objects, logs):
        if obj is None:
            return [], log.read_text(errors="replace")
    return objects, ""


@dataclass
class Finding:
    kind: str                      # heap-buffer-overflow, signed-integer-overflow, ...
    where: str                     # file.c:line of the student's frame
    function: str
    message: str
    tests: list[str] = field(default_factory=list)
    speculative: bool = True       # every occurrence was in a speculative test
    compensated: bool = False      # a signed overflow, and every normal test it hit passed
    _normal_ok: bool = True
    _normal_seen: bool = False

    @property
    def overflow(self) -> bool:
        return self.kind == "signed-integer-overflow"


FRAME = re.compile(r"#\d+ 0x[0-9a-f]+ in (\S+) (\S+?):(\d+)(?::\d+)?")
UBSAN = re.compile(r"^(\S+?):(\d+):\d+: runtime error: (.*)$", re.M)
ASAN = re.compile(r"ERROR: AddressSanitizer: ([\w-]+)")


def _kind(message: str) -> str:
    for key, name in (("signed integer overflow", "signed-integer-overflow"),
                      ("negation of", "signed-integer-overflow"), ("shift", "shift"),
                      ("out of bounds", "out-of-bounds"), ("division", "division"),
                      ("misaligned", "misaligned"), ("not a valid value", "invalid-value"),
                      ("outside the range", "float-cast-overflow"), ("pointer overflow", "pointer-overflow")):
        if key in message:
            return name
    return "undefined-behavior"


def _student(path: str, root: Path) -> str | None:
    try:
        resolved = Path(path).resolve()
    except OSError:
        return None
    return resolved.relative_to(root.resolve()).as_posix() if resolved.is_relative_to(root.resolve()) else None


def collect(directory: Path, root: Path, passed=None) -> list[Finding]:
    """Reports of one run, grouped by kind and location. `passed(suite, index)`
    gives the normal-pass verdict of a test (True: right result, None: unknown)."""
    tests: dict[str, tuple[str, bool, str, int]] = {}
    mapping = directory / "tests.tsv"
    if mapping.is_file():
        for line in mapping.read_text(errors="replace").splitlines():
            parts = line.split("\t")
            if len(parts) >= 5:      # seq, suite, spec, index in suite, name
                tests[parts[0]] = (f"{parts[1]} · {parts[4]}", parts[2] == "1", parts[1],
                                   int(parts[3]) if parts[3].isdigit() else 0)
            elif len(parts) == 4:    # seq, suite, spec, name
                tests[parts[0]] = (f"{parts[1]} · {parts[3]}", parts[2] == "1", parts[1], 0)
    findings: dict[tuple[str, str], Finding] = {}

    def add(kind: str, where: str, function: str, message: str, test: str, spec: bool, ok: bool | None) -> None:
        item = findings.setdefault((kind, where), Finding(kind, where, function, message))
        if test not in item.tests:
            item.tests.append(test)
        item.speculative &= spec
        # out-of-range inputs (speculative tests) overflow by themselves: only
        # the normal tests tell whether the overflows cancel out
        if not spec:
            item._normal_seen = True
            item._normal_ok &= ok is True
        item.compensated = item.overflow and item._normal_seen and item._normal_ok

    for report in sorted(directory.glob("[tr]*.*")):
        if report.name == "tests.tsv":
            continue
        seq = report.name[1:].split(".", 1)[0]
        test, spec, suite, index = tests.get(seq, (report.name, False, "", 0))
        ok = passed(suite, index) if passed else None
        text = report.read_text(errors="replace")
        # several UB reports per file (the program goes on after each one)
        matches = list(UBSAN.finditer(text))
        for position, match in enumerate(matches):
            end = matches[position + 1].start() if position + 1 < len(matches) else len(text)
            block = text[match.start():end]
            frames = [(fn, _student(path, root), line) for fn, path, line in FRAME.findall(block)]
            own = next(((fn, f"{rel}:{line}") for fn, rel, line in frames if rel), None)
            rel = _student(match.group(1), root)
            if not rel and not own:
                continue            # inside the tester or the libc
            where = f"{rel}:{match.group(2)}" if rel else own[1]
            add(_kind(match.group(3)), where, own[0] if own else "?", match.group(3).strip(), test, spec, ok)
        asan = ASAN.search(text)
        if asan:
            block = text[asan.start():]
            frames = [(fn, _student(path, root), line) for fn, path, line in FRAME.findall(block)]
            own = next(((fn, f"{rel}:{line}") for fn, rel, line in frames if rel), None)
            if own:
                access = re.search(r"^(READ|WRITE) of size (\d+)", block, re.M)
                message = asan.group(1) + (f" ({access.group(1)} of {access.group(2)} bytes)" if access else "")
                add(asan.group(1), own[1], own[0], message, test, spec, ok)
    return sorted(findings.values(), key=lambda f: (f.compensated, f.speculative, f.where))


def merge(into: list[Finding], items: list[Finding], prefix: str = "") -> None:
    """Findings of several runs (GNL: one per BUFFER_SIZE) into one list."""
    for item in items:
        tests = [f"{prefix}{name.split(' · ', 1)[-1]}" if prefix else name for name in item.tests]
        same = next((m for m in into if (m.kind, m.where) == (item.kind, item.where)), None)
        if same is None:
            item.tests = tests
            into.append(item)
            continue
        same.tests += [name for name in tests if name not in same.tests]
        same.speculative &= item.speculative
        if item._normal_seen:
            same._normal_ok = (same._normal_ok if same._normal_seen else True) and item._normal_ok
            same._normal_seen = True
        same.compensated = same.overflow and same._normal_seen and same._normal_ok


def workers() -> int:
    """Parallel shards for the slow passes (valgrind, sanitizers)."""
    return max(1, min(os.cpu_count() or 1, 8))


# One slot per core for every background process (valgrind, sanitizer shards,
# push_swap runs): many jobs can be submitted at once without overloading the
# machine, and none waits behind a small fixed pool.
SLOTS = threading.BoundedSemaphore(max(1, os.cpu_count() or 1))


def run_slot(ctx: Context, args: list[str], *, timeout: int, **popen) -> subprocess.Popen | None:
    """Start one background process when a core is free, wait for it, free the
    core; counts it in the progress line. Returns the finished process."""
    with SLOTS:
        process = subprocess.Popen(args, start_new_session=True, **popen)
        ctx.track(process)
        try:
            process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
    ctx.shard_done()
    return process


def run_sharded(ctx: Context, directory: Path, command, env_for, timeout: int) -> list[Path]:
    """Run `command(shard_dir)` once per shard (--shard K/N: tests split between
    N processes, --split: big FUZZ tests cut in N slices), each in its own
    thread as soon as a core is free. Returns the shard dirs."""
    shutil.rmtree(directory, ignore_errors=True)
    total = workers()
    dirs = []
    ctx.shard_started(total)
    threads = []
    for k in range(total):
        shard = directory / f"s{k}"
        shard.mkdir(parents=True)
        dirs.append(shard)

        def one(shard: Path = shard, k: int = k) -> None:
            with open(shard / "output.log", "w") as log:
                run_slot(ctx, [*command(shard), "--shard", f"{k}/{total}", "--split", str(total)],
                         timeout=timeout, cwd=ctx.build, env=env_for(shard), stdout=log,
                         stderr=subprocess.STDOUT)
        thread = threading.Thread(target=one, daemon=True)
        thread.start()
        threads.append(thread)
    for thread in threads:
        thread.join()
    return dirs


def execute(ctx: Context, executable: Path, args: list[str | Path], name: str,
            skip: str = "") -> list[Path]:
    """Run the sanitized tester silently, in parallel shards (thread-safe).
    `skip`: test names left out (timed tests whose waiting adds no coverage)."""
    return run_sharded(ctx, ctx.build / "sanitize" / name,
                       lambda shard: [str(a) for a in (executable, *ctx.engine_args(), *args,
                                                       *(["--skip-name", skip] if skip else []))],
                       lambda shard: environment(ctx, shard), 1800)


def gather(ctx: Context, dirs: list[Path]) -> list[Finding]:
    """Findings of an executed run, judged with the normal pass's verdicts
    (ctx.renderer.results): call it once the normal pass is displayed."""
    results = getattr(ctx.renderer, "results", {})

    def passed(suite: str, index: int) -> bool | None:
        res = results.get((suite, index))
        return None if res is None else res in (0, 1)
    findings: list[Finding] = []
    for shard in dirs:
        merge(findings, collect(shard, ctx.options.directory, passed))
    return sorted(findings, key=lambda f: (f.compensated, f.speculative, f.where))


def run(ctx: Context, executable: Path, args: list[str | Path], name: str) -> list[Finding]:
    return gather(ctx, execute(ctx, executable, args, name))


def write(ctx: Context, findings: list[Finding], *, skipped: str = "", label: str = "",
          title: str = "SANITIZERS · -fsanitize=address,undefined", tool: str = "ASan + UBSan",
          clean: str = "") -> Path:
    """SANITIZERS (or VALGRIND) records, in the format of the checks report."""
    report = CheckReport()
    t = ctx.message
    report.section(title + (f" · {label}" if label else ""))
    # ASan and UBSan both see an out-of-bounds stack/global write: keep ASan's
    asan_at = {item.where for item in findings if "overflow" in item.kind and not item.overflow}
    findings = [item for item in findings if not (item.kind == "out-of-bounds" and item.where in asan_at)]
    if skipped:
        report.check("SKIP", tool, skipped)
    elif not findings:
        report.check("OK", tool, clean or t("no overflow, out-of-bounds access or undefined behavior",
                                            "aucun overflow, accès hors limites ni comportement indéfini"))
    for item in findings:
        if item.compensated:
            # the overflows cancel out: every test it happened in got the right result
            report.check("OK", f"{item.function}", f"{item.where} · " + t(
                "signed overflow that cancels out (right result in every test)",
                "overflow signé qui s'annule (bon résultat dans chaque test)"))
        else:
            report.check("WARN" if item.speculative else "KO", f"{item.function}", f"{item.where} · {item.message}")
        more = len(item.tests) - 1
        report.detail(t("test: ", "test : ") + item.tests[0] + (t(f" (+{more} other)", f" (+{more} autre(s))") if more > 0 else ""))
    path = ctx.build / "sanitize" / f"records-{os.getpid()}-{tool.split()[0]}-{label or 'all'}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    report.write(path)
    return path


def push_swap_start(ctx: Context, *, bonus: bool):
    """The push_swap -fsanitize pass in the background (it compares with the
    normal binary itself, so it needs no verdict): a future of its records."""
    if not ctx.options.sanitize:
        return None
    return ctx.background(lambda: push_swap_pass(ctx, bonus=bonus))


def push_swap_pass(ctx: Context, *, bonus: bool) -> Path | None:
    """push_swap is a program: its sources are rebuilt with the sanitizers and
    run on sorts (each strategy, 3 to 500 numbers), errors, --bench and the
    checker, all runs at the same time; every report becomes a finding."""
    import random
    from .subject.common import compiled_sources, header_dirs
    from .subject.push_swap import LEAK_RUNS
    if not ctx.options.sanitize:
        return None
    if not available(ctx):
        return write(ctx, [], skipped=ctx.message("this compiler cannot link -fsanitize=address,undefined",
                                                  "ce compilateur ne sait pas lier -fsanitize=address,undefined"))
    root = ctx.options.directory
    directory = ctx.build / "sanitize" / "runs"
    shutil.rmtree(directory, ignore_errors=True)
    directory.mkdir(parents=True)
    programs: dict[str, Path] = {}
    for program, rule in (("push_swap", "all"), ("checker", "bonus")):
        if program == "checker" and not bonus:
            continue
        dry = subprocess.run(["make", "--no-print-directory", "-C", str(root), "-nB", rule], env=ctx.env,
                             capture_output=True, text=True, check=False).stdout
        sources = [root / name for name in sorted(compiled_sources(root, dry))]
        out = ctx.build / "sanitize" / f"obj-{program}"
        objects, _ = compile_objects(ctx, sources, out, includes=header_dirs(root))
        binary = out / program
        if not objects or ctx.command([*ctx.cc, *LINK_FLAGS, *objects, "-lm", "-o", binary],
                                      log=out / "link.log"):
            return write(ctx, [], skipped=ctx.message(f"{program}: sources do not build alone; see ",
                                                      f"{program} : les sources ne compilent pas seules ; voir ")
                         + str(out))
        programs[program] = binary
    rng = random.Random(ctx.options.seed)
    runs: list[tuple[str, list[str], str | None]] = list(LEAK_RUNS)
    for flag in ("--simple", "--medium", "--complex", "--adaptive", "--bench"):
        for n in (3, 5, 100, 500):
            runs.append(("push_swap", [flag, *map(str, rng.sample(range(-100000, 100000), n))], None))
    runs.append(("push_swap", ["-2147483648", "2147483647", "0", "-1", "1"], None))
    runs.append(("push_swap", ["2147483647", "-2147483648"], None))
    env = environment(ctx, directory)
    mapping = []
    same: dict[tuple[str, int], bool] = {}

    def execute(binary: Path, args: list[str], stdin: str | None, run_env: dict[str, str]):
        try:
            with SLOTS:
                done = subprocess.run([str(binary), *args], input=(stdin or "").encode(), env=run_env,
                                      cwd=root, capture_output=True, timeout=60, check=False)
            return done.returncode, done.stdout, done.stderr
        except subprocess.TimeoutExpired:
            return None

    def one(index: int, program: str, args: list[str], stdin: str | None) -> None:
        run_env = dict(env)
        for key in ("ASAN_OPTIONS", "UBSAN_OPTIONS"):
            run_env[key] += f":log_path={directory}/t{index}"
        sanitized = execute(programs[program], args, stdin, run_env)
        # an overflow cancels out when the program still prints exactly what
        # the normal build prints (the tests already checked that output)
        normal = execute(root / program, args, stdin, ctx.env) if (root / program).is_file() else None
        same[(program, index)] = sanitized is not None and sanitized == normal
        ctx.shard_done()
    todo = [(index, program, args, stdin) for index, (program, args, stdin) in enumerate(runs)
            if program in programs]
    for index, program, args, stdin in todo:
        shown = " ".join(args) if len(args) < 12 else " ".join(args[:10]) + f" … ({len(args)})"
        mapping.append(f"{index}\t{program}\t0\t{index}\t./{program} {shown}" + (f" < {stdin!r}" if stdin else ""))
    ctx.shard_started(len(todo))
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max(1, os.cpu_count() or 1)) as pool:
        list(pool.map(lambda job: one(*job), todo))
    (directory / "tests.tsv").write_text("\n".join(mapping) + "\n")
    findings = collect(directory, root, lambda suite, index: same.get((suite, index)))
    for item in findings:
        item.tests = [name.split(" · ", 1)[-1] for name in item.tests]
    return write(ctx, findings)
