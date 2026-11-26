"""push_swap: build the student's binaries with make, run the C suites on them."""
from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess

from .archive import ArchiveProject
from ..subject.push_swap import push_swap_checks
from ..runtime import Context, RunnerError


@dataclass(frozen=True)
class PushSwapProject(ArchiveProject):
    def validate(self, ctx: Context) -> None:
        # The subject imposes no header name: only the Makefile is required.
        if not (ctx.options.directory / "Makefile").is_file():
            raise RunnerError(f"{ctx.options.directory}: Makefile " + ctx.message("not found", "introuvable"))
        if ctx.options.part is not None and ctx.options.part not in self.parts:
            raise RunnerError(ctx.message("Invalid part for", "Partie invalide pour") + f" {self.name}")

    def official_checker(self, ctx: Context) -> tuple[Path | None, str]:
        """The 42 checker_linux, copied executable into build/ (the original is
        left as it is). Returns (copy, where it came from) or (None, reason)."""
        if ctx.options.checker:
            candidates = [Path(ctx.options.checker).expanduser()]
        else:
            candidates = [ctx.options.directory / "checker_linux", ctx.root / "checker_linux",
                          Path.home() / "Downloads/checker_linux", Path.home() / "Téléchargements/checker_linux"]
        source = next((path for path in candidates if path.is_file()), None)
        if source is None:
            if ctx.options.checker:
                raise RunnerError(f"--checker: {ctx.options.checker} " + ctx.message("not found", "introuvable"))
            return None, ctx.message("checker_linux not found (--checker PATH)",
                                     "checker_linux introuvable (--checker CHEMIN)")
        copy = ctx.build / "checker_linux"
        ctx.build.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, copy)
        copy.chmod(0o755)
        try:
            probe = subprocess.run([str(copy), "2", "1"], input="sa\n", capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            probe = None
        if probe is None or probe.stdout != "OK\n":
            return None, ctx.message(f"{source} does not answer OK to a valid sort",
                                     f"{source} ne répond pas OK à un tri valide")
        return copy, str(source)

    def checks(self, ctx: Context) -> None:
        push_swap_checks(ctx, self)

    def build(self, ctx: Context, rule: str = "all") -> None:
        """make all -> ./push_swap; make bonus -> ./checker (on top of it)."""
        binary = "checker" if rule == "bonus" else "push_swap"
        if rule != "bonus":
            self.make(ctx, "fclean", log="fclean.log")
        if self.make(ctx, rule) or not (ctx.options.directory / binary).is_file():
            raise RunnerError(f"make {rule}: " + ctx.message("see", "voir") + f" {ctx.build / 'make.log'}")

    def run(self, ctx: Context) -> int:
        self.build(ctx)
        bonus = ctx.options.part != 1 and self.has_bonus(ctx)
        note = None
        failed = 0
        if bonus:
            try:
                self.build(ctx, "bonus")
            except RunnerError:
                bonus, failed = False, 1
                note = ctx.message("Bonus not tested: make bonus gave no ./checker.",
                                   "Bonus non testé : make bonus ne donne pas de ./checker.")
        elif ctx.options.part != 1:
            note = ctx.message("Bonus not tested: no bonus rule.", "Bonus non testé : pas de règle bonus.")
        if ctx.options.part == 2 and not bonus:
            raise RunnerError(note or "")
        checker, where = self.official_checker(ctx)
        if checker:
            print("   ▶ " + ctx.message("official checker: ", "checker officiel : ") + where
                  + ctx.message(" (confirms the 100 / 500 sorts)", " (confirme les tris de 100 / 500)"), flush=True)
        else:
            print("   ▶ " + where, flush=True)
        from .push_swap_tests import run_push_swap_suites
        return max(failed, run_push_swap_suites(ctx, bonus=bonus, checker=checker, note=note))

    def cleanup(self, ctx: Context) -> None:
        if self.make(ctx, "fclean", log="fclean.log") == 0:
            print("   ▶ " + ctx.message("make fclean: object files and binaries removed",
                                        "make fclean : .o et binaires supprimés") + "\n", flush=True)


PROJECT = PushSwapProject(key="push_swap", name="push_swap", aliases=("ps",), header="push_swap.h",
                          subject="1.2", archive="push_swap", source_dir="push_swap")
