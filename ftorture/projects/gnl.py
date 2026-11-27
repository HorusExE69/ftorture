"""Source-only strategy: one isolated binary per BUFFER_SIZE and part."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import gzip
import re

from .base import Project
from .. import sanitize, valgrind
from ..subject.gnl import gnl_checks
from ..runtime import Context, RunnerError

MANDATORY_SIZES = ("1", "2", "3", "5", "7", "10", "42", "100", "1024", "9999",
                   "100000", "10000000", "def", "0")
BONUS_SIZES = ("1", "42", "9999", "10000000")
CUSTOM_SLOTS = 8            # other BUFFER_SIZEs in -f: src/gnl/proj.c slots bsc1..8
FILE_MAX = 16               # --file entries: src/gnl/t_gnl_custom.c
SIZE_MAX = 256 * 1024 * 1024
UNITS = {"": 1, "k": 1000, "m": 1000 ** 2}            # BUFFER_SIZE: 100k = 100000
FILE_UNITS = {"": 1, "k": 1024, "m": 1024 ** 2, "g": 1024 ** 3}   # file sizes


def buffer_size(token: str) -> str | None:
    """'42', '100k', '10M', 'def' -> canonical string; None if not a size."""
    token = token.strip().lower()
    if token == "def":
        return token
    match = re.fullmatch(r"(\d+)([km]?)", token)
    return str(int(match.group(1)) * UNITS[match.group(2)]) if match else None


def file_entry(token: str, base: Path) -> tuple[str, int]:
    """--file value -> ('path', 0) for an existing file, ('size', bytes) for '500k'."""
    path = (base / token).expanduser()
    if path.is_file():
        return str(path.resolve()), 0
    match = re.fullmatch(r"(\d+)\s*([kmg]?)(?:o|b)?", token.strip().lower())
    if match and int(match.group(1)):
        return "", int(match.group(1)) * FILE_UNITS[match.group(2)]
    raise ValueError(token)


class GnlProject(Project):
    def validate(self, ctx: Context) -> None:
        super().validate(ctx)
        if ctx.options.functions:
            tokens = [token for token in ctx.options.functions.split(",") if token.strip()]
            unknown = [token for token in tokens if buffer_size(token) is None]
            if unknown:
                raise RunnerError(ctx.message("Unknown BUFFER_SIZE (a number ≥ 0, 100k, 10M or def): ",
                                              "BUFFER_SIZE inconnu (un nombre ≥ 0, 100k, 10M ou def) : ")
                                  + ", ".join(unknown))
            if len(self.custom_sizes(ctx)) > CUSTOM_SLOTS:
                raise RunnerError(ctx.message(f"At most {CUSTOM_SLOTS} BUFFER_SIZEs outside the usual list.",
                                              f"Au plus {CUSTOM_SLOTS} BUFFER_SIZE hors de la liste habituelle."))
        if len(ctx.options.files) > FILE_MAX:
            raise RunnerError(ctx.message(f"At most {FILE_MAX} --file.", f"Au plus {FILE_MAX} --file."))
        for token in ctx.options.files:
            try:
                path, size = file_entry(token, Path.cwd())
            except ValueError:
                raise RunnerError(ctx.message("--file: not a file nor a size (500, 64k, 2M): ",
                                              "--file : ni un fichier ni une taille (500, 64k, 2M) : ") + token) from None
            if size > SIZE_MAX:
                raise RunnerError(ctx.message("--file: at most 256M", "--file : 256M au maximum") + f" ({token})")

    def selected(self, ctx: Context) -> list[str] | None:
        if not ctx.options.functions:
            return None
        sizes = [buffer_size(token) for token in ctx.options.functions.split(",") if token.strip()]
        return list(dict.fromkeys(size for size in sizes if size is not None))

    def custom_sizes(self, ctx: Context) -> list[str]:
        """Selected sizes that have no line of their own in the usual list."""
        return [size for size in self.selected(ctx) or () if size not in MANDATORY_SIZES]

    def checks(self, ctx: Context) -> None:
        gnl_checks(ctx, self.header, self.subject)

    def passes(self, ctx: Context, bonus: bool) -> list[tuple[int, str, str]]:
        selected = self.selected(ctx)
        custom = self.custom_sizes(ctx)
        result = []
        for part, sizes in ((1, MANDATORY_SIZES), (2, BONUS_SIZES)):
            if (ctx.options.part and ctx.options.part != part) or (part == 2 and not bonus):
                continue
            prefix = "b" if part == 2 else ""
            result += [(part, size, f"{prefix}bs{size}") for size in sizes if selected is None or size in selected]
            # other sizes: their own slot, in the mandatory and the bonus part
            result += [(part, size, f"{prefix}bsc{slot}") for slot, size in enumerate(custom, 1)]
        return result

    def files(self, ctx: Context) -> tuple[str, int]:
        """FTORTURE_GNL_FILES for the C suite, and the largest input in bytes."""
        lines, largest = [], 0
        for token in ctx.options.files:
            path, size = file_entry(token, Path.cwd())
            lines.append(f"path:{path}" if path else f"size:{size}")
            largest = max(largest, size or Path(path).stat().st_size)
        return "\n".join(lines), largest

    def bible(self, ctx: Context) -> list[str]:
        """data/bible-kjv.txt.gz decompressed once into build/: -D Z_BIBLE."""
        source = ctx.root / "data/bible-kjv.txt.gz"
        if not source.is_file():
            return []
        target = ctx.build / "bible-kjv.txt"
        if not target.is_file() or target.stat().st_mtime < source.stat().st_mtime:
            with gzip.open(source, "rb") as compressed:
                ctx.build.mkdir(parents=True, exist_ok=True)
                target.write_bytes(compressed.read())
        return ["-D", f'Z_BIBLE="{target}"']

    @staticmethod
    def timeout(size: str, largest: int) -> int:
        """Default per-test timeout of one pass: 10 s, more for a big --file read
        with a small BUFFER_SIZE: one read() per BUFFER_SIZE bytes, ~10 µs each
        with the tester's instrumentation and a malloc per read (measured ~8 µs),
        plus ~50 ns per byte. Capped at 10 min; --timeout overrides it."""
        buffer = 42 if size == "def" else max(1, min(int(size), 4096))
        return min(600, 10 + int(largest / buffer * 1e-5 + largest * 5e-8))

    def prestart(self, ctx: Context) -> None:
        """Everything starts now (builds, normal passes, valgrind, sanitizers),
        while the checks run; run() then only displays. Not with -e: the
        normal passes are timed and must run alone."""
        if not ctx.options.efficiency:
            ctx.slow["gnl"] = ctx.background(self._launch, ctx)

    def run(self, ctx: Context) -> int:
        future = ctx.slow.pop("gnl", None)
        state = future.result() if future else self._launch(ctx)
        try:
            return self._display(ctx, state)
        except KeyboardInterrupt:
            ctx.stop_background()
            raise
        finally:
            for pool in state.get("pools", ()):
                pool.shutdown(wait=False, cancel_futures=True)

    def _launch(self, ctx: Context) -> dict:
        bonus = all((ctx.options.directory / name).is_file() for name in (
            "get_next_line_bonus.c", "get_next_line_utils_bonus.c", "get_next_line_bonus.h"))
        passes = self.passes(ctx, bonus)
        if not passes:
            raise RunnerError(ctx.message("No BUFFER_SIZE selected or bonus sources missing.",
                                          "Aucun BUFFER_SIZE sélectionné ou sources bonus absentes."))
        flags = ctx.engine_flags("gnl")
        bible = self.bible(ctx)
        files, largest = self.files(ctx)
        san_ok = ctx.options.sanitize and sanitize.available(ctx)
        vg_ok = ctx.options.valgrind and valgrind.available()
        # memcheck is ~20x slower: BUFFER_SIZE 1 and 42 (or the first selected) per part
        vg_sizes = {part: ({"1", "42"} & {size for p, size, _ in passes if p == part})
                    or {next(size for p, size, _ in passes if p == part)}
                    for part in {p for p, _, _ in passes}}
        if files:
            ctx.env["FTORTURE_GNL_FILES"] = files
        for source in ("engine", "memtrack"):
            ctx.require([*ctx.cc, *flags, "-c", ctx.root / "src" / f"{source}.c",
                         "-o", ctx.build / f"{source}.o"], ctx.build / f"{source}.log")

        def build(item: tuple[int, str, str]) -> dict:
            """One BUFFER_SIZE: your two files, the tester, its -fsanitize twin."""
            part, size, key = item
            out = ctx.build / key
            out.mkdir(exist_ok=True)
            suffix = "_bonus" if part == 2 else ""
            definitions = [] if size == "def" else ["-D", f"BUFFER_SIZE={size}"]
            slot = ["-D", f"Z_SLOT={key.rsplit('c', 1)[1]}", "-D", f'Z_LABEL="BUFFER_SIZE={size}"'] \
                if "bsc" in key else []
            job = {"part": part, "size": size, "key": key, "out": out, "error": None, "exe": None, "san": None,
                   "label": f"BUFFER_SIZE={size}" + (" (bonus)" if part == 2 else "")}
            objects = []
            for name in (f"get_next_line{suffix}", f"get_next_line_utils{suffix}"):
                # -g: valgrind and the replays show your file:line (cached in build/cache)
                obj = ctx.cached_object(ctx.options.directory / f"{name}.c",
                                        ["-Wall", "-Wextra", "-Werror", "-g", *definitions,
                                         f"-I{ctx.options.directory}"], out / f"{name}.log")
                if obj is None:
                    job["error"] = "compile"
                    return job
                objects.append(obj)
            tests = [ctx.root / "src/gnl" / name for name in ("gnl.c", "proj.c", "t_gnl.c", "b_gnl.c",
                                                              "t_gnl_custom.c")]
            if part == 2:
                tests.append(ctx.root / "src/gnl/t_gnl_bonus.c")
            defines = [*flags, "-D", f"Z_BS={-1 if size == 'def' else size}", "-D", f"GNL_SUITE={key}",
                       *slot, *bible]
            test_objects = [ctx.cached_object(test, defines, out / f"{test.stem}.log") for test in tests]
            if None in test_objects:
                job["error"] = "link"
                return job
            common = [ctx.build / "engine.o", ctx.build / "memtrack.o", *test_objects]
            wraps = ["-Wl,--wrap=malloc", "-Wl,--wrap=free", "-Wl,--wrap=read"]
            if not ctx.compile([*common, *objects, *wraps, "-lm", "-o", out / "tester"], out / "link.log"):
                job["error"] = "link"
                return job
            job["exe"] = out / "tester"
            args = ["-f", key]
            if ctx.options.timeout is None:
                args.extend(["--timeout", str(self.timeout(size, largest))])
            if files:
                # --file: only your files, for each selected BUFFER_SIZE
                args.extend(["--name", "ton fichier :,fichier généré :"])
            if size == "0" or (size != "def" and int(size) >= 10000000):
                args.append("--spec-pass")
            job["args"] = args
            # -fsanitize (not 0 and 10M+: no line read / a buffer that big on the stack)
            if san_ok and size != "0" and (size == "def" or int(size) < 10000000):
                built, _ = sanitize.compile_objects(
                    ctx, [ctx.options.directory / f"{name}{suffix}.c" for name in
                          ("get_next_line", "get_next_line_utils")], out / "san",
                    defines=definitions, includes=[ctx.options.directory])
                if built and ctx.compile([*common, *built, *wraps, *sanitize.LINK_FLAGS, "-lm",
                                          "-o", out / "tester-san"], out / "san-link.log"):
                    job["san"] = out / "tester-san"
            return job

        # Every BUFFER_SIZE is independent: build them all at once, then start
        # the normal passes, the sanitizers and valgrind at the same time (one
        # process per core, sanitize.SLOTS); _display shows the normal passes in
        # their usual order as they finish.
        with ThreadPoolExecutor(sanitize.workers()) as pool:
            jobs = list(pool.map(build, passes))
        # -e times the code: then nothing else may run at the same time
        timed = ctx.options.efficiency
        # every normal pass at once (sanitize.SLOTS keeps one process per core):
        # a pool of 8 made the 18 passes run in 3 waves
        runs = ThreadPoolExecutor(1 if timed else max(1, len(jobs)))
        slow = ThreadPoolExecutor(32)

        def normal_run(job: dict):
            if timed:
                return ctx.capture_tester(job["exe"], job["args"], function_filter=False)
            with sanitize.SLOTS:
                return ctx.capture_tester(job["exe"], job["args"], function_filter=False)
        normal = {job["key"]: runs.submit(normal_run, job) for job in jobs if job["exe"]}
        late = []
        if timed:
            for future in normal.values():
                future.result()
        for job in jobs:
            if not job["exe"]:
                continue
            if vg_ok and job["size"] in vg_sizes.get(job["part"], ()):
                # the Bible, the 10 000 / 100 000 / 300 000 lines and the big files take
                # minutes under memcheck with a small buffer (a quadratic stash x the
                # ~30x of valgrind) and go through the same code as the shorter lines
                late.append(("vg", job, slow.submit(
                    valgrind.execute, ctx, job["exe"], job["args"], job["key"],
                    "Bible,ligne longue (10 000,100 000,lit le minimum,gros fichier,5 000 lignes")))
            if job["san"]:
                # "ligne de 100 000 en moins de 3 s" waits up to 3 s on a quadratic
                # stash: it times the code, the sanitizers already see that code
                # through the 4096 and 10 000 character lines
                late.append(("san", job, slow.submit(sanitize.execute, ctx, job["san"], job["args"], job["key"],
                                                     "en moins de 3 s")))
        return {"jobs": jobs, "normal": normal, "late": late, "pools": (runs, slow), "bonus": bonus,
                "vg_ok": vg_ok, "san_ok": san_ok}

    def _display(self, ctx: Context, state: dict) -> int:
        jobs, normal, late, bonus = state["jobs"], state["normal"], state["late"], state["bonus"]
        vg_ok, san_ok = state["vg_ok"], state["san_ok"]
        shown = False
        failed = False
        for job in jobs:
            if job["error"]:
                size = job["size"]
                if job["error"] == "compile":
                    accepted = size == "0" and not ctx.options.speculative
                    failed |= not accepted
                    print(f"{'▲' if accepted else '✘'} BUFFER_SIZE={size}: " + ctx.message(
                        "compilation failed; see", "échec de compilation ; voir") + f" {job['out']}",
                        flush=True)
                else:
                    failed = True
                    print(f"✘ BUFFER_SIZE={size}: " + ctx.message(
                        "cannot link tester; see", "impossible de lier le tester ; voir")
                        + f" {job['out'] / 'link.log'}", flush=True)
                continue
            status, lines = normal[job["key"]].result()
            ctx.replay_tester(lines, checks=not shown)
            shown = True
            if status > 1:
                return status
        vg_findings: list = []
        san_findings: list = []
        for kind, job, future in late:
            dirs = ctx.wait(future)       # "▶ valgrind + sanitizers… 37/160"
            if kind == "vg":
                sanitize.merge(vg_findings, valgrind.gather(ctx, dirs), f"{job['label']} · ")
            else:
                sanitize.merge(san_findings, sanitize.gather(ctx, dirs), f"{job['label']} · ")
        if not shown:
            if ctx.options.checks:
                ctx.renderer.render_checks(ctx.checks_file)
            return ctx.renderer.finish(extra_failed=True)
        if ctx.options.valgrind:
            ctx.renderer.render_records(valgrind.records(ctx, vg_findings, skipped="" if vg_ok else ctx.message(
                "valgrind not installed", "valgrind non installé")))
        if ctx.options.sanitize:
            ctx.renderer.render_records(sanitize.write(ctx, san_findings, skipped="" if san_ok else ctx.message(
                "this compiler cannot link -fsanitize=address,undefined",
                "ce compilateur ne sait pas lier -fsanitize=address,undefined")))
        if not bonus and ctx.options.part != 1:
            ctx.renderer.add_note(ctx.message("Bonus not tested: bonus files missing.",
                                              "Bonus non testé : fichiers bonus absents."))
        return ctx.renderer.finish(extra_failed=failed)


# The subject asks for the three files at the root: no subfolder search.
PROJECT = GnlProject(key="gnl", name="get_next_line", aliases=("get_next_line",),
                     header="get_next_line.h", subject="14.3", nested=False)
