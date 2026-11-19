from .archive import ArchiveProject
from ..subject.archive import archive_checks
from ..runtime import Context


class LibftProject(ArchiveProject):
    def checks(self, ctx: Context) -> None:
        archive_checks(ctx, self, linked_list=True)

    def run(self, ctx: Context) -> int:
        self.build_archive(ctx)
        executable = self.link(ctx)
        args = ["-p", str(ctx.options.part)] if ctx.options.part else []
        return ctx.tester(executable, args, checks=True)


PROJECT = LibftProject(key="libft", name="libft", header="libft.h", subject="19.3",
                       parts=(1, 2, 3), archive="libft.a", source_dir="libft")
