"""Build strategy shared by Makefile/archive-based projects."""
from dataclasses import dataclass
from pathlib import Path
import subprocess

from .base import Project
from ..runtime import Context, RunnerError


@dataclass(frozen=True)
class ArchiveProject(Project):
    archive: str = ""
    source_dir: str = ""
    symbol_prefix: str = "ft_"
    tools: tuple[str, ...] = ("make", "nm")
    requires_makefile: bool = True

    def validate(self, ctx: Context) -> None:
        super().validate(ctx)
        if not (ctx.options.directory / "Makefile").is_file():
            raise RunnerError(f"{ctx.options.directory}: Makefile " + ctx.message(
                "not found", "introuvable"))

    def make(self, ctx: Context, rule: str, *, log: str = "make.log") -> int:
        return ctx.command(["make", "--no-print-directory", "-C", ctx.options.directory, rule],
                           log=ctx.build / log)

    def has_bonus(self, ctx: Context) -> bool:
        return ctx.command(["make", "--no-print-directory", "-C", ctx.options.directory,
                            "-n", "bonus"], log=ctx.build / "bonus-rule.log") == 0

    def build_archive(self, ctx: Context, rule: str = "all") -> None:
        self.make(ctx, "fclean", log="fclean.log")
        if self.make(ctx, rule) or not (ctx.options.directory / self.archive).is_file():
            raise RunnerError(f"make {rule}: " + ctx.message("see", "voir") + f" {ctx.build / 'make.log'}")

    def extra_archives(self, ctx: Context) -> list[Path]:
        return []

    def link(self, ctx: Context, name: str = "tester", *, archive: Path | None = None,
             flags: tuple[str, ...] = ()) -> Path:
        archive = archive or ctx.options.directory / self.archive
        result = subprocess.run(["nm", "--defined-only", str(archive)], env=ctx.env,
                                capture_output=True, text=True, check=False)
        if result.returncode:
            raise RunnerError(f"nm: {result.stderr.strip()}")
        symbols = sorted({columns[-1] for line in result.stdout.splitlines()
                          if len(columns := line.split()) >= 3
                          and columns[-2] == "T" and columns[-1].startswith(self.symbol_prefix)})
        executable = ctx.build / name
        # the tester's own sources: compiled once (build/cache), in parallel
        from concurrent.futures import ThreadPoolExecutor
        sources = [ctx.root / "src/engine.c", ctx.root / "src/memtrack.c",
                   *sorted((ctx.root / "src" / self.source_dir).glob("*.c"))]
        logs = ctx.build / "objects"
        logs.mkdir(exist_ok=True)
        with ThreadPoolExecutor(8) as pool:
            objects = list(pool.map(lambda source: ctx.cached_object(
                source, ctx.engine_flags(self.source_dir), logs / f"{source.stem}.log"), sources))
        if None in objects:
            bad = sources[objects.index(None)]
            raise RunnerError(ctx.message("Command failed; see", "Échec ; voir") + f" {logs / (bad.stem + '.log')}")
        args = [*ctx.cc, *objects,
                "-Wl,--wrap=malloc", "-Wl,--wrap=free",
                *(f"-Wl,-u,{symbol}" for symbol in symbols), archive, *self.extra_archives(ctx),
                *flags, "-lm", "-o", executable]
        ctx.require(args, ctx.build / "link.log")
        return executable

    def sanitized(self, ctx: Context, rule: str, args: list[str], label: str = "") -> Path | None:
        """-fsanitize pass on the sources `make -nB <rule>` compiles, rebuilt by
        ftorture with ASan + UBSan into a private archive; same tests, silent."""
        from .. import sanitize
        from ..subject.common import compiled_sources, header_dirs
        if not ctx.options.sanitize:
            return None
        if not sanitize.available(ctx):
            return sanitize.write(ctx, [], label=label, skipped=ctx.message(
                "this compiler cannot link -fsanitize=address,undefined",
                "ce compilateur ne sait pas lier -fsanitize=address,undefined"))
        root = ctx.options.directory
        dry = subprocess.run(["make", "--no-print-directory", "-C", str(root), "-nB", rule], env=ctx.env,
                             capture_output=True, text=True, check=False).stdout
        sources = [root / name for name in sorted(compiled_sources(root, dry))]
        out = ctx.build / "sanitize" / f"obj-{rule}"
        objects, error = sanitize.compile_objects(ctx, sources, out, includes=header_dirs(root))
        if not objects:
            return sanitize.write(ctx, [], label=label, skipped=ctx.message(
                "sources do not compile alone; see ", "les sources ne compilent pas seules ; voir ") + str(out))
        archive = out / f"san-{self.archive}"
        archive.unlink(missing_ok=True)
        ctx.require(["ar", "rcs", archive, *objects], out / "ar.log")
        executable = self.link(ctx, f"tester-san-{rule}", archive=archive, flags=sanitize.LINK_FLAGS)
        return sanitize.write(ctx, sanitize.run(ctx, executable, args, rule), label=label)

    def memchecked(self, ctx: Context, rule: str, args: list[str], label: str = "") -> Path | None:
        """valgrind pass: the sources of `make -nB <rule>` rebuilt with -g (so
        every error has its file:line even without -g in the Makefile), the
        same tests, memtrack off so valgrind's malloc sees every block."""
        from .. import sanitize, valgrind
        from ..subject.common import compiled_sources, header_dirs
        if not ctx.options.valgrind:
            return None
        if not valgrind.available():
            return valgrind.records(ctx, [], label=label, skipped=ctx.message(
                "valgrind not installed", "valgrind non installé"))
        root = ctx.options.directory
        dry = subprocess.run(["make", "--no-print-directory", "-C", str(root), "-nB", rule], env=ctx.env,
                             capture_output=True, text=True, check=False).stdout
        sources = [root / name for name in sorted(compiled_sources(root, dry))]
        out = ctx.build / "valgrind" / f"obj-{rule}"
        objects, _ = sanitize.compile_objects(ctx, sources, out, includes=header_dirs(root), flags=("-g", "-O0"))
        if not objects:
            return valgrind.records(ctx, [], label=label, skipped=ctx.message(
                "sources do not compile alone; see ", "les sources ne compilent pas seules ; voir ") + str(out))
        archive = out / f"g-{self.archive}"
        archive.unlink(missing_ok=True)
        ctx.require(["ar", "rcs", archive, *objects], out / "ar.log")
        executable = self.link(ctx, f"tester-g-{rule}", archive=archive)
        return valgrind.records(ctx, valgrind.run(ctx, executable, args, rule), label=label)

    def cleanup(self, ctx: Context) -> None:
        status = self.make(ctx, "fclean", log="fclean.log")
        if status == 0:
            print("   ▶ " + ctx.message("make fclean: object files and archive removed",
                                        "make fclean : .o et archive supprimés") + "\n", flush=True)
