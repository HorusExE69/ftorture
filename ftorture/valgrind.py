"""valgrind pass: the same tests under memcheck, like at the evaluation.

The tester runs with memtrack off (valgrind's malloc sees every block), each
test child writes `pid<pid>` so its `vg.<pid>` log is tied to its test, and
every memcheck error in the student's code becomes a VALGRIND line:

- Invalid read / Invalid write (one byte past a block, use after free…);
- Conditional jump / Use of uninitialised value / Syscall param … uninitialised:
  attributed to the student's malloc that created the value (--track-origins),
  e.g. a calloc that is not zeroed, a string without its '\\0';
- Invalid free, Mismatched free, Source and destination overlap.

Not reported here: NULL dereferences and crashes identical to the libc (the
normal tests compare them), errors only in tests whose normal verdict was a
libc-matching crash, and leaks (memtrack reports them).
"""
from pathlib import Path
import re
import shutil
import subprocess

from .runtime import Context
from .sanitize import Finding, write as write_records

ERROR = re.compile(r"^==\d+== (Invalid (?:read|write) of size \d+|Invalid free\(\) / delete / delete\[\] / realloc\(\)"
                   r"|Mismatched free\(\) / delete / delete \[\]|Conditional jump or move depends on uninitialised "
                   r"value\(s\)|Use of uninitialised value of size \d+|Syscall param .* uninitialised byte\(s\)"
                   r"|Source and destination overlap in \S+)", re.M)
FRAME = re.compile(r"(?:at|by) 0x[0-9A-F]+: (\S+) \((\S+?):(\d+)\)")
NULLISH = re.compile(r"Address 0x([0-9a-f]+) is not stack'd, malloc'd or \(recently\) free'd")


def available() -> bool:
    return shutil.which("valgrind") is not None


def _student(path: str, root: Path) -> str | None:
    try:
        resolved = Path(path).resolve()
    except OSError:
        return None
    base = root.resolve()
    return resolved.relative_to(base).as_posix() if resolved.is_relative_to(base) else None


def _own(block: str, root: Path) -> tuple[str, str] | None:
    for function, path, line in FRAME.findall(block):
        rel = _student(path, root)
        if rel:
            return function, f"{rel}:{line}"
    return None


def collect(directory: Path, root: Path, results: dict | None = None) -> list[Finding]:
    tests: dict[str, tuple[str, bool, str, int]] = {}
    mapping = directory / "tests.tsv"
    if mapping.is_file():
        for line in mapping.read_text(errors="replace").splitlines():
            parts = line.split("\t")
            if len(parts) >= 5:
                tests[parts[0]] = (f"{parts[1]} · {parts[4]}", parts[2] == "1", parts[1],
                                   int(parts[3]) if parts[3].isdigit() else 0)
    findings: dict[tuple[str, str], Finding] = {}
    for log in sorted(directory.glob("vg.*")):
        pid = log.name.split(".", 1)[1]
        owner = directory / f"pid{pid}"
        if not owner.is_file():
            continue                         # the parent process
        seq, ref = (owner.read_text().split() + ["0", "0"])[:2]
        if ref != "0":
            continue                         # the libc reference run
        test, spec, suite, index = tests.get(seq, (f"#{seq}", False, "", 0))
        if results is not None and results.get((suite, index)) == 1:
            continue                         # crash identical to the libc: accepted
        text = log.read_text(errors="replace")
        matches = list(ERROR.finditer(text))
        for position, match in enumerate(matches):
            end = matches[position + 1].start() if position + 1 < len(matches) else len(text)
            block = text[match.start():end]
            null = NULLISH.search(block)
            if null and int(null.group(1), 16) < 4096:
                continue                     # NULL (+ small offset): the normal tests decide
            kind = match.group(1)
            origin = block.split("Uninitialised value was created", 1)
            used = _own(origin[0], root)
            created = _own(origin[1], root) if len(origin) == 2 else None
            # uninitialised: where it is used (often the tester's own read,
            # then only the student's malloc is known) and where it was made
            own = used or created
            if own is None:
                continue                     # not in the student's code
            message = kind
            if created:
                message = f"{kind} (value from the malloc of {created[0]}, {created[1]})"
            item = findings.setdefault((kind.split(" of size")[0], own[1]),
                                       Finding("valgrind", own[1], own[0], message))
            if test not in item.tests:
                item.tests.append(test)
            item.speculative &= spec
    return sorted(findings.values(), key=lambda f: (f.speculative, f.where))


def execute(ctx: Context, executable: Path, args: list[str | Path], name: str,
            skip: str = "") -> list[Path]:
    """memcheck in parallel shards (thread-safe). `skip`: test names left out
    (heavy tests that add nothing for memcheck)."""
    from .sanitize import run_sharded

    def command(shard: Path) -> list[str]:
        return ["valgrind", "--tool=memcheck", "--error-limit=no", "--track-origins=yes",
                "--leak-check=no", "--fullpath-after=", f"--log-file={shard}/vg.%p",
                *(str(a) for a in (executable, *ctx.engine_args(), *args)), "--timeout", "120",
                *(["--skip-name", skip] if skip else [])]

    def env_for(shard: Path) -> dict[str, str]:
        env = dict(ctx.env)
        env["FTORTURE_SAN_DIR"] = str(shard)
        return env
    return run_sharded(ctx, ctx.build / "valgrind" / name, command, env_for, 3600)


def gather(ctx: Context, dirs: list[Path]) -> list[Finding]:
    from .sanitize import merge
    findings: list[Finding] = []
    for shard in dirs:
        merge(findings, collect(shard, ctx.options.directory, getattr(ctx.renderer, "results", None)))
    return sorted(findings, key=lambda f: (f.speculative, f.where))


def run(ctx: Context, executable: Path, args: list[str | Path], name: str,
        skip: str = "") -> list[Finding]:
    return gather(ctx, execute(ctx, executable, args, name, skip))


def records(ctx: Context, findings: list[Finding], *, label: str = "", skipped: str = "") -> Path:
    path = write_records(ctx, findings, label=label, skipped=skipped, title="VALGRIND · memcheck",
                         tool="memcheck", clean=ctx.message("no invalid read / write, uninitialised value or bad free",
                                           "aucune lecture / écriture invalide, valeur non initialisée ni free invalide"))
    return path
