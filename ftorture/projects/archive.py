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
             flags: tuple[str, ...] = (), extra: bool = True) -> Path:
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
                *(f"-Wl,-u,{symbol}" for symbol in symbols), archive, *(self.extra_archives(ctx) if extra else ()),
                *flags, "-lm", "-o", executable]
        ctx.require(args, ctx.build / "link.log")
        return executable

    # ---- valgrind and -fsanitize passes ------------------------------------
    # Both rebuild the sources `make -nB <rule>` compiles into a private archive
    # (-g for valgrind, ASan + UBSan for the sanitizers) and run the same tests
    # silently. They are started in the background before the checks
    # (prestart) and only read once the normal pass has been displayed.
    def slow_rules(self, ctx: Context) -> list[tuple[str, list[str], str]]:
        """(make rule, tester args, label) of the passes to check."""
        args = ["-p", str(ctx.options.part)] if ctx.options.part else []
        return [("all", args, "")]

    def _slow_job(self, ctx: Context, kind: str, rule: str, args: list[str], extra: bool) -> tuple[str, object]:
        """Build and run one slow pass (thread-safe): ("dirs", shard dirs),
        ("skip", reason) or ("retry", reason) when linking needs libft.a."""
        from .. import sanitize, valgrind
        from ..subject.common import compiled_sources, header_dirs
        if kind == "vg" and not valgrind.available():
            return "skip", ctx.message("valgrind not installed", "valgrind non installé")
        if kind == "san" and not sanitize.available(ctx):
            return "skip", ctx.message("this compiler cannot link -fsanitize=address,undefined",
                                       "ce compilateur ne sait pas lier -fsanitize=address,undefined")
        root = ctx.options.directory
        dry = subprocess.run(["make", "--no-print-directory", "-C", str(root), "-nB", rule], env=ctx.env,
                             capture_output=True, text=True, check=False).stdout
        sources = [root / name for name in sorted(compiled_sources(root, dry))]
        out = ctx.build / ("valgrind" if kind == "vg" else "sanitize") / f"obj-{rule}"
        flags = ("-g", "-O0") if kind == "vg" else sanitize.SAN_FLAGS
        objects, _ = sanitize.compile_objects(ctx, sources, out, includes=header_dirs(root), flags=flags)
        if not objects:
            return "skip", ctx.message("sources do not compile alone; see ",
                                       "les sources ne compilent pas seules ; voir ") + str(out)
        archive = out / f"{kind}-{self.archive}"
        archive.unlink(missing_ok=True)
        ctx.require(["ar", "rcs", archive, *objects], out / "ar.log")
        try:
            executable = self.link(ctx, f"tester-{kind}-{rule}", archive=archive, extra=extra,
                                   flags=() if kind == "vg" else sanitize.LINK_FLAGS)
        except RunnerError as error:
            return ("retry" if not extra else "skip"), str(error)
        if kind == "vg":
            return "dirs", valgrind.execute(ctx, executable, args, rule)
        return "dirs", sanitize.execute(ctx, executable, args, rule)

    def prestart(self, ctx: Context) -> None:
        """Start the slow passes now, while the checks and the normal tests run
        (not with -e: nothing may run while the code is timed)."""
        if ctx.options.efficiency:
            return
        for rule, args, _ in self.slow_rules(ctx):
            for kind, enabled in (("vg", ctx.options.valgrind), ("san", ctx.options.sanitize)):
                if enabled:
                    ctx.slow[(kind, rule)] = ctx.background(self._slow_job, ctx, kind, rule, args, False)

    def slow_pass(self, ctx: Context, kind: str, rule: str, args: list[str], label: str = "") -> Path | None:
        from .. import sanitize, valgrind
        if not (ctx.options.valgrind if kind == "vg" else ctx.options.sanitize):
            return None
        future = ctx.slow.pop((kind, rule), None)
        state, value = ctx.wait(future) if future else self._slow_job(ctx, kind, rule, args, True)
        if state == "retry":        # its libft.a was not built yet: link it now
            state, value = self._slow_job(ctx, kind, rule, args, True)
        if kind == "vg":
            return valgrind.records(ctx, valgrind.gather(ctx, value) if state == "dirs" else [], label=label,
                                    skipped="" if state == "dirs" else str(value))
        return sanitize.write(ctx, sanitize.gather(ctx, value) if state == "dirs" else [], label=label,
                              skipped="" if state == "dirs" else str(value))

    def sanitized(self, ctx: Context, rule: str, args: list[str], label: str = "") -> Path | None:
        return self.slow_pass(ctx, "san", rule, args, label)

    def memchecked(self, ctx: Context, rule: str, args: list[str], label: str = "") -> Path | None:
        return self.slow_pass(ctx, "vg", rule, args, label)

    def cleanup(self, ctx: Context) -> None:
        status = self.make(ctx, "fclean", log="fclean.log")
        if status == 0:
            print("   ▶ " + ctx.message("make fclean: object files and archive removed",
                                        "make fclean : .o et archive supprimés") + "\n", flush=True)
