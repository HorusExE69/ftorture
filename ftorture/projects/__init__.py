"""Explicit project registry: adding a project requires no CLI changes."""
from pathlib import Path

from .base import Project
from .gnl import PROJECT as GNL
from .libft import PROJECT as LIBFT
from .printf import PROJECT as PRINTF

PROJECTS: tuple[Project, ...] = (LIBFT, PRINTF, GNL)


def find(name: str) -> Project | None:
    from ..registry import Registry
    return Registry(PROJECTS).find(name)


def detect(directory: Path) -> Project | None:
    from ..registry import Registry
    return Registry(PROJECTS).detect(directory)
