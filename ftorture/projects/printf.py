from pathlib import Path

from .archive import ArchiveProject
from ..subject.archive import archive_checks
from ..runtime import Context, RunnerError


class PrintfProject(ArchiveProject):
    def checks(self, ctx: Context) -> None:
        archive_checks(ctx, self, algorithm=True)

    def extra_archives(self, ctx: Context) -> list[Path]:
        libft = ctx.options.directory / "libft/libft.a"
        return [libft] if libft.is_file() else []

    def run(self, ctx: Context) -> int:
        bonus = self.has_bonus(ctx) and ctx.options.part != 1
        mandatory = ctx.options.part != 2
        if not mandatory and not bonus:
            raise RunnerError(ctx.message("No bonus rule; no tests selected.",
                                          "Pas de règle bonus ; aucun test sélectionné."))
        first = True
        status = 0
        for part, rule in ((1, "all"), (2, "bonus")):
            if (part == 1 and not mandatory) or (part == 2 and not bonus):
                continue
            self.build_archive(ctx, rule)
            executable = self.link(ctx, f"tester-{part}")
            args = ["-p", str(part)]
            if not first:
                args.extend(["--stats-in", ctx.stats, "--no-legend", "--no-banner"])
            if part == 1 and bonus:
                args.extend(["--no-summary", "--stats-out", ctx.stats])
            elif part == 1 and ctx.options.part != 1:
                args.extend(["--note", ctx.message("Bonus not tested: no bonus rule.",
                                                   "Bonus non testé : pas de règle bonus.")])
            result = ctx.tester(executable, args, checks=first)
            if result > 1:
                return result
            status = max(status, result)
            first = False
        return status


PROJECT = PrintfProject(key="printf", name="ft_printf", aliases=("ft_printf",),
                       header="ft_printf.h", subject="12.1", archive="libftprintf.a",
                       source_dir="printf")
