"""Source-only strategy: one isolated binary per BUFFER_SIZE and part."""
from pathlib import Path
import gzip
import re

from .base import Project
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

    def run(self, ctx: Context) -> int:
        bonus = all((ctx.options.directory / name).is_file() for name in (
            "get_next_line_bonus.c", "get_next_line_utils_bonus.c", "get_next_line_bonus.h"))
        passes = self.passes(ctx, bonus)
        if not passes:
            raise RunnerError(ctx.message("No BUFFER_SIZE selected or bonus sources missing.",
                                          "Aucun BUFFER_SIZE sélectionné ou sources bonus absentes."))
        flags = ctx.engine_flags("gnl")
        bible = self.bible(ctx)
        files, largest = self.files(ctx)
        if files:
            ctx.env["FTORTURE_GNL_FILES"] = files
        for source in ("engine", "memtrack"):
            ctx.require([*ctx.cc, *flags, "-c", ctx.root / "src" / f"{source}.c",
                         "-o", ctx.build / f"{source}.o"], ctx.build / f"{source}.log")
        last = None
        previous_part = None
        failed = False
        for part, size, key in passes:
            out = ctx.build / key
            out.mkdir(exist_ok=True)
            suffix = "_bonus" if part == 2 else ""
            objects = []
            definitions = [] if size == "def" else ["-D", f"BUFFER_SIZE={size}"]
            slot = ["-D", f"Z_SLOT={key.rsplit('c', 1)[1]}", "-D", f'Z_LABEL="BUFFER_SIZE={size}"'] \
                if "bsc" in key else []
            compiled = True
            for name in (f"get_next_line{suffix}", f"get_next_line_utils{suffix}"):
                obj = out / f"{name}.o"
                if not ctx.compile(["-Wall", "-Wextra", "-Werror", *definitions,
                                    f"-I{ctx.options.directory}", "-c",
                                    ctx.options.directory / f"{name}.c", "-o", obj],
                                   out / f"{name}.log"):
                    compiled = False
                    break
                objects.append(obj)
            if not compiled:
                accepted = size == "0" and not ctx.options.speculative
                failed |= not accepted
                print(f"{'▲' if accepted else '✘'} BUFFER_SIZE={size}: " + ctx.message(
                    "compilation failed; see", "échec de compilation ; voir") + f" {out}", flush=True)
                continue
            tests = [ctx.root / "src/gnl" / name for name in ("gnl.c", "proj.c", "t_gnl.c", "b_gnl.c",
                                                              "t_gnl_custom.c")]
            if part == 2:
                tests.append(ctx.root / "src/gnl/t_gnl_bonus.c")
            executable = out / "tester"
            if not ctx.compile([*flags, "-D", f"Z_BS={-1 if size == 'def' else size}",
                         "-D", f"GNL_SUITE={key}", *slot, *bible, ctx.build / "engine.o", ctx.build / "memtrack.o",
                         *tests, *objects, "-Wl,--wrap=malloc", "-Wl,--wrap=free", "-Wl,--wrap=read",
                         "-lm", "-o", executable], out / "link.log"):
                failed = True
                print(f"✘ BUFFER_SIZE={size}: " + ctx.message(
                    "cannot link tester; see", "impossible de lier le tester ; voir") + f" {out / 'link.log'}", flush=True)
                continue
            args = ["-f", key]
            if ctx.options.timeout is None:
                args.extend(["--timeout", str(self.timeout(size, largest))])
            if files:
                # --file: only your files, for each selected BUFFER_SIZE
                args.extend(["--name", "ton fichier :,fichier généré :"])
            if size == "0" or (size != "def" and int(size) >= 10000000):
                args.append("--spec-pass")
            result = ctx.stream_tester(executable, args, checks=last is None, function_filter=False)
            if result > 1:
                return result
            last = executable
            previous_part = part
        if last is None:
            if ctx.options.checks:
                ctx.renderer.render_checks(ctx.checks_file)
            return ctx.renderer.finish(extra_failed=True)
        if not bonus and ctx.options.part != 1:
            ctx.renderer.add_note(ctx.message("Bonus not tested: bonus files missing.",
                                              "Bonus non testé : fichiers bonus absents."))
        return ctx.renderer.finish(extra_failed=failed)


# The subject asks for the three files at the root: no subfolder search.
PROJECT = GnlProject(key="gnl", name="get_next_line", aliases=("get_next_line",),
                     header="get_next_line.h", subject="14.3", nested=False)
