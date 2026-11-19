"""A single registry interface for bundled projects and user-owned test suites."""
from pathlib import Path

from .projects import PROJECTS
from .projects.base import Project
from .runtime import RunnerError


class Registry:
    def __init__(self, projects=PROJECTS):
        self.projects = tuple(projects)
        names = set()
        for project in self.projects:
            for name in (project.key, *project.aliases):
                if name in names:
                    raise RunnerError(f"Duplicate project name or alias: {name}")
                names.add(name)

    def find(self, name: str | None) -> Project | None:
        return next((project for project in self.projects if name in (project.key, *project.aliases)), None)

    def detect(self, directory: Path) -> Project | None:
        priority = {"gnl": 0, "printf": 1, "libft": 2}
        return next((project for project in sorted(self.projects, key=lambda p: priority.get(p.key, 3))
                     if not project.custom and project.header and (directory / project.header).is_file()), None)


def load_registry(custom_directory: Path | None = None) -> Registry:
    # Lazy import keeps the bundled registry independent of the custom strategy.
    from .projects.custom import discover
    return Registry((*PROJECTS, *discover(custom_directory)))
