"""Project interface: metadata, validation, checks, execution and cleanup."""
from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..runtime import Context, RunnerError


@dataclass(frozen=True)
class Project(ABC):
    key: str
    name: str
    header: str
    subject: str
    parts: tuple[int, ...] = (1, 2)
    aliases: tuple[str, ...] = ()
    tools: tuple[str, ...] = ("nm",)
    check_tools: tuple[str, ...] = ()
    requires_compiler: bool = True
    requires_makefile: bool = False
    custom: bool = False

    def validate(self, ctx: Context) -> None:
        if not (ctx.options.directory / self.header).is_file():
            raise RunnerError(f"{ctx.options.directory}: {self.header} " + ctx.message(
                "not found", "introuvable"))
        if ctx.options.part is not None and ctx.options.part not in self.parts:
            raise RunnerError(ctx.message("Invalid part for", "Partie invalide pour") + f" {self.name}")

    def checks(self, ctx: Context) -> None:
        # Explicit opt-in: new modules must not inherit another subject's checks.
        raise RunnerError(f"{self.name}: subject checks are not implemented")

    def cleanup(self, ctx: Context) -> None:
        """Release project artifacts owned by the build strategy, if any."""

    @abstractmethod
    def run(self, ctx: Context) -> int:
        """Build and execute test passes; return their combined exit status."""
