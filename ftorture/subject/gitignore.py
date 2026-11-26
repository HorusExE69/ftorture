"""The .gitignore rules of a student folder, without git.

What the repository ignores is never pushed, so it is not part of the submission:
the file, include and norm checks skip it. Every .gitignore in the tree applies to
its own directory, deeper files win, the last matching line wins, `!` re-includes,
and nothing inside an ignored directory can be re-included (as in git).
"""
from pathlib import Path
import re


def _translate(pattern: str) -> str:
    """Glob of a .gitignore line -> regex on a path relative to its .gitignore."""
    out, i = [], 0
    while i < len(pattern):
        c = pattern[i]
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("/**", i) and i + 3 == len(pattern):
            out.append("/.*")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif c == "*":
            out.append("[^/]*")
            i += 1
        elif c == "?":
            out.append("[^/]")
            i += 1
        elif c == "[":
            end = pattern.find("]", i + 2 if pattern[i + 1:i + 2] in ("!", "^") else i + 1)
            if end < 0:
                out.append(re.escape(c))
                i += 1
            else:
                body = pattern[i + 1:end]
                if body[:1] in ("!", "^"):
                    body = "^" + body[1:]
                out.append("[" + body.replace("\\", "\\\\") + "]")
                i = end + 1
        elif c == "\\" and i + 1 < len(pattern):
            out.append(re.escape(pattern[i + 1]))
            i += 2
        else:
            out.append(re.escape(c))
            i += 1
    return "".join(out)


class Rule:
    def __init__(self, line: str) -> None:
        self.negated = line.startswith("!")
        if self.negated:
            line = line[1:]
        self.directory_only = line.endswith("/")
        line = line.rstrip("/")
        anchored = "/" in line
        line = line.lstrip("/")
        body = _translate(line)
        # Without a slash the pattern matches a name at any depth.
        self.regex = re.compile(("" if anchored else "(?:.*/)?") + body + r"\Z", re.S)

    def matches(self, relative: str, is_dir: bool) -> bool:
        return (is_dir or not self.directory_only) and bool(self.regex.match(relative))


def parse(text: str) -> list[Rule]:
    rules = []
    for raw in text.splitlines():
        line = raw.rstrip("\n\r")
        # trailing spaces are ignored unless escaped
        while line.endswith(" ") and not line.endswith("\\ "):
            line = line[:-1]
        if not line or line.startswith("#"):
            continue
        if line.startswith(("\\#", "\\!")):
            line = line[1:]
        if line in ("/", "!"):
            continue
        try:
            rules.append(Rule(line))
        except re.error:
            continue
    return rules


class GitIgnore:
    """Rules found while walking `root`; call `enter(directory)` before its entries."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.rules: dict[Path, list[Rule]] = {}

    def enter(self, directory: Path) -> None:
        path = directory / ".gitignore"
        if directory not in self.rules:
            try:
                self.rules[directory] = parse(path.read_text(errors="replace")) if path.is_file() else []
            except OSError:
                self.rules[directory] = []

    def ignored(self, path: Path, is_dir: bool) -> bool:
        """Only the entry itself: the caller does not walk into ignored folders."""
        verdict = False
        bases = [self.root, *(self.root / Path(*path.relative_to(self.root).parts[:k])
                              for k in range(1, len(path.relative_to(self.root).parts)))]
        for base in bases:
            relative = path.relative_to(base).as_posix()
            for rule in self.rules.get(base, ()):
                if rule.matches(relative, is_dir):
                    verdict = not rule.negated
        return verdict
