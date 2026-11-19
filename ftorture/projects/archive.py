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

    def link(self, ctx: Context, name: str = "tester") -> Path:
        archive = ctx.options.directory / self.archive
        result = subprocess.run(["nm", "--defined-only", str(archive)], env=ctx.env,
                                capture_output=True, text=True, check=False)
        if result.returncode:
            raise RunnerError(f"nm: {result.stderr.strip()}")
        symbols = sorted({columns[-1] for line in result.stdout.splitlines()
                          if len(columns := line.split()) >= 3
                          and columns[-2] == "T" and columns[-1].startswith(self.symbol_prefix)})
        executable = ctx.build / name
        args = [*ctx.cc, *ctx.engine_flags(self.source_dir), ctx.root / "src/engine.c",
                ctx.root / "src/memtrack.c", *sorted((ctx.root / "src" / self.source_dir).glob("*.c")),
                "-Wl,--wrap=malloc", "-Wl,--wrap=free",
                *(f"-Wl,-u,{symbol}" for symbol in symbols), archive, *self.extra_archives(ctx),
                "-o", executable]
        ctx.require(args, ctx.build / "link.log")
        return executable

    def cleanup(self, ctx: Context) -> None:
        status = self.make(ctx, "clean", log="clean.log")
        if status == 0:
            print("   ▶ " + ctx.message("make clean: object files removed", "make clean : .o supprimés") + "\n", flush=True)
