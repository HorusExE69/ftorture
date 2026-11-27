"""Explicit project registry: adding a project requires no CLI changes."""
from pathlib import Path

from .base import Project
from .gnl import PROJECT as GNL
from .libft import PROJECT as LIBFT
from .printf import PROJECT as PRINTF
from .push_swap import PROJECT as PUSH_SWAP
from .py00 import PROJECT as PY00
from .py01 import PROJECT as PY01
from .py02 import PROJECT as PY02

PROJECTS: tuple[Project, ...] = (LIBFT, PRINTF, GNL, PUSH_SWAP, PY00, PY01, PY02)


def find(name: str) -> Project | None:
    from ..registry import Registry
    return Registry(PROJECTS).find(name)


def detect(directory: Path) -> Project | None:
    from ..registry import Registry
    return Registry(PROJECTS).detect(directory)
