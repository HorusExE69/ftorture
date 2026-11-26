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
        for part, rule in ((1, "all"), (2, "bonus")):
            if (part == 1 and not mandatory) or (part == 2 and not bonus):
                continue
            self.build_archive(ctx, rule)
            executable = self.link(ctx, f"tester-{part}")
            result = ctx.stream_tester(executable, ["-p", str(part)], checks=first)
            if result > 1:
                return result
            first = False
        if not bonus and ctx.options.part != 1:
            ctx.renderer.add_note(ctx.message("Bonus not tested: no bonus rule.",
                                              "Bonus non testé : pas de règle bonus."))
        return ctx.renderer.finish()


PROJECT = PrintfProject(key="printf", name="ft_printf", aliases=("ft_printf",),
                       header="ft_printf.h", subject="12.1", archive="libftprintf.a",
                       source_dir="printf")
