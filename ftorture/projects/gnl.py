"""Source-only strategy: one isolated binary per BUFFER_SIZE and part."""
from .base import Project
from ..subject.gnl import gnl_checks
from ..runtime import Context, RunnerError

MANDATORY_SIZES = ("1", "2", "3", "5", "7", "10", "42", "100", "1024", "9999",
                   "100000", "10000000", "def", "0")
BONUS_SIZES = ("1", "42", "9999", "10000000")


class GnlProject(Project):
    def validate(self, ctx: Context) -> None:
        super().validate(ctx)
        if ctx.options.functions:
            unknown = set(ctx.options.functions.split(",")) - set(MANDATORY_SIZES)
            if unknown:
                raise RunnerError("Unknown BUFFER_SIZE: " + ", ".join(sorted(unknown)))

    def checks(self, ctx: Context) -> None:
        gnl_checks(ctx, self.header, self.subject)

    def passes(self, ctx: Context, bonus: bool) -> list[tuple[int, str, str]]:
        selected = set(ctx.options.functions.split(",")) if ctx.options.functions else None
        return [(part, size, f"{'b' if part == 2 else ''}bs{size}")
                for part, sizes in ((1, MANDATORY_SIZES), (2, BONUS_SIZES))
                if (not ctx.options.part or ctx.options.part == part) and (part == 1 or bonus)
                for size in sizes if selected is None or size in selected]

    def run(self, ctx: Context) -> int:
        bonus = all((ctx.options.directory / name).is_file() for name in (
            "get_next_line_bonus.c", "get_next_line_utils_bonus.c", "get_next_line_bonus.h"))
        passes = self.passes(ctx, bonus)
        if not passes:
            raise RunnerError(ctx.message("No BUFFER_SIZE selected or bonus sources missing.",
                                          "Aucun BUFFER_SIZE sélectionné ou sources bonus absentes."))
        flags = ctx.engine_flags("gnl")
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
            tests = [ctx.root / "src/gnl" / name for name in ("gnl.c", "proj.c", "t_gnl.c")]
            if part == 2:
                tests.append(ctx.root / "src/gnl/t_gnl_bonus.c")
            executable = out / "tester"
            if not ctx.compile([*flags, "-D", f"Z_BS={-1 if size == 'def' else size}",
                         "-D", f"GNL_SUITE={key}", ctx.build / "engine.o", ctx.build / "memtrack.o",
                         *tests, *objects, "-Wl,--wrap=malloc", "-Wl,--wrap=free", "-Wl,--wrap=read",
                         "-o", executable], out / "link.log"):
                failed = True
                print(f"✘ BUFFER_SIZE={size}: " + ctx.message(
                    "cannot link tester; see", "impossible de lier le tester ; voir") + f" {out / 'link.log'}", flush=True)
                continue
            args = ["-f", key, "--no-summary", "--stats-out", ctx.stats]
            if ctx.options.timeout is None:
                args.extend(["--timeout", "10"])
            if last is not None:
                args.extend(["--stats-in", ctx.stats, "--no-legend", "--no-banner"])
            if part == previous_part:
                args.append("--no-section")
            if size in ("0", "10000000"):
                args.append("--spec-pass")
            result = ctx.tester(executable, args, checks=last is None, function_filter=False)
            if result > 1:
                return result
            last = executable
            previous_part = part
        if last is None:
            return 1
        args = ["--no-banner", "--no-legend", "--no-section", "--stats-in", ctx.stats,
                "-f", "__resume__"]
        if not bonus and ctx.options.part != 1:
            args.extend(["--note", ctx.message("Bonus not tested: bonus files missing.",
                                               "Bonus non testé : fichiers bonus absents.")])
        return max(int(failed), ctx.tester(last, args, function_filter=False))


PROJECT = GnlProject(key="gnl", name="get_next_line", aliases=("get_next_line",),
                     header="get_next_line.h", subject="14.3")
