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

from .checks import CheckReport
from .runtime import Context

SAN_FLAGS = ("-fsanitize=address,undefined", "-fno-sanitize=null,nonnull-attribute,returns-nonnull-attribute,pointer-overflow",
             "-fno-sanitize-recover=undefined", "-fno-omit-frame-pointer", "-g", "-O0")
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
    env["UBSAN_OPTIONS"] = "print_stacktrace=1:halt_on_error=1"
    return env


def compile_objects(ctx: Context, sources: list[Path], out: Path, *, defines: list[str] = (),
                    includes: list[Path] = ()) -> tuple[list[Path], str]:
    """Each source compiled with the sanitizers. Returns (objects, error log)."""
    out.mkdir(parents=True, exist_ok=True)
    objects = []
    for index, source in enumerate(sources):
        obj = out / f"{index:03d}-{source.stem}.o"
        log = out / f"{index:03d}-{source.stem}.log"
        if ctx.command([*ctx.cc, *SAN_FLAGS, "-w", *defines, *(f"-I{d}" for d in includes),
                        "-c", source, "-o", obj], log=log):
            return [], log.read_text(errors="replace")
        objects.append(obj)
    return objects, ""


@dataclass
class Finding:
    kind: str                      # heap-buffer-overflow, signed-integer-overflow, ...
    where: str                     # file.c:line of the student's frame
    function: str
    message: str
    tests: list[str] = field(default_factory=list)
    speculative: bool = True       # every occurrence was in a speculative test


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


def collect(directory: Path, root: Path) -> list[Finding]:
    tests: dict[str, tuple[str, bool]] = {}
    mapping = directory / "tests.tsv"
    if mapping.is_file():
        for line in mapping.read_text(errors="replace").splitlines():
            parts = line.split("\t", 3)
            if len(parts) == 4:
                tests[parts[0]] = (f"{parts[1]} · {parts[3]}", parts[2] == "1")
    findings: dict[tuple[str, str], Finding] = {}
    for report in sorted(directory.glob("[tr]*.*")):
        if report.name == "tests.tsv":
            continue
        seq = report.name[1:].split(".", 1)[0]
        test, spec = tests.get(seq, (report.name, False))
        text = report.read_text(errors="replace")
        frames = [(fn, _student(path, root), line) for fn, path, line in FRAME.findall(text)]
        own = next(((fn, f"{rel}:{line}") for fn, rel, line in frames if rel), None)
        match = UBSAN.search(text)
        if match:
            rel = _student(match.group(1), root)
            where = f"{rel}:{match.group(2)}" if rel else (own[1] if own else match.group(1))
            kind, message = _kind(match.group(3)), match.group(3).strip()
            function = own[0] if own else "?"
            if not rel and not own:
                continue                # inside the tester or the libc
        else:
            asan = ASAN.search(text)
            if not asan or not own:
                continue
            kind = asan.group(1)
            access = re.search(r"^(READ|WRITE) of size (\d+)", text, re.M)
            message = f"{kind}" + (f" ({access.group(1)} of {access.group(2)} bytes)" if access else "")
            function, where = own
        item = findings.setdefault((kind, where), Finding(kind, where, function, message))
        if test not in item.tests:
            item.tests.append(test)
        item.speculative &= spec
    return sorted(findings.values(), key=lambda f: (f.speculative, f.where))


def run(ctx: Context, executable: Path, args: list[str | Path], name: str) -> list[Finding]:
    """Run the sanitized tester silently; returns the findings."""
    directory = ctx.build / "sanitize" / name
    shutil.rmtree(directory, ignore_errors=True)
    directory.mkdir(parents=True)
    command = [str(a) for a in (executable, *ctx.engine_args(), *args)]
    with open(directory / "output.log", "w") as log:
        try:
            subprocess.run(command, cwd=ctx.build, env=environment(ctx, directory), stdout=log,
                           stderr=subprocess.STDOUT, timeout=1800, check=False, start_new_session=True)
        except subprocess.TimeoutExpired:
            pass
    return collect(directory, ctx.options.directory)


def write(ctx: Context, findings: list[Finding], *, skipped: str = "", label: str = "") -> Path:
    """SANITIZERS records, in the format of the checks report."""
    report = CheckReport()
    t = ctx.message
    report.section("SANITIZERS · -fsanitize=address,undefined" + (f" · {label}" if label else ""))
    if skipped:
        report.check("SKIP", "ASan + UBSan", skipped)
    elif not findings:
        report.check("OK", "ASan + UBSan", t("no overflow, out-of-bounds access or undefined behavior",
                                             "aucun overflow, accès hors limites ni comportement indéfini"))
    for item in findings:
        status = "WARN" if item.speculative else "KO"
        report.check(status, f"{item.function}", f"{item.where} · {item.message}")
        more = len(item.tests) - 1
        report.detail(t("test: ", "test : ") + item.tests[0] + (t(f" (+{more} other)", f" (+{more} autre(s))") if more > 0 else ""))
    path = ctx.build / "sanitize" / f"records-{os.getpid()}-{label or 'all'}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    report.write(path)
    return path


def push_swap_pass(ctx: Context, *, bonus: bool) -> Path | None:
    """push_swap is a program: its sources are rebuilt with the sanitizers and
    run on sorts (each strategy, 3 to 500 numbers), errors, --bench and the
    checker; every report becomes a finding."""
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
    for index, (program, args, stdin) in enumerate(runs):
        if program not in programs:
            continue
        shown = " ".join(args) if len(args) < 12 else " ".join(args[:10]) + f" … ({len(args)})"
        mapping.append(f"{index}\t{program}\t0\t./{program} {shown}" + (f" < {stdin!r}" if stdin else ""))
        run_env = dict(env)
        for key in ("ASAN_OPTIONS", "UBSAN_OPTIONS"):
            run_env[key] += f":log_path={directory}/t{index}"
        try:
            subprocess.run([str(programs[program]), *args], input=(stdin or "").encode(), env=run_env,
                           cwd=root, capture_output=True, timeout=60, check=False)
        except subprocess.TimeoutExpired:
            pass
    (directory / "tests.tsv").write_text("\n".join(mapping) + "\n")
    findings = collect(directory, root)
    for item in findings:
        item.tests = [name.split(" · ", 1)[-1] for name in item.tests]
    return write(ctx, findings)
