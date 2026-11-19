"""Conservative include-use analysis, with compiler-derived system symbols.

This is a heuristic, not a C parser: unknown/unresolvable headers get no verdict.
Header dependencies are followed as a graph, including cycles and indirect users.
"""
from pathlib import Path
import re

from ..checks import CheckSession
from .common import project_files

IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_]*"
KEYWORDS = set(("auto break case char const continue default do double else enum extern float for goto "
                "if inline int long register restrict return short signed sizeof static struct switch "
                "typedef union unsigned void volatile while asm _Bool _Atomic _Alignas _Alignof").split())
COMMON = {"NULL", "size_t", "ssize_t", "wchar_t", "ptrdiff_t", "off_t", "pid_t", "va_list"}
C_PARTS = re.compile(r'/\*[\s\S]*?\*/|//[^\n]*|"(?:\\[\s\S]|[^"\\])*"|\'(?:\\[\s\S]|[^\'\\])*\'')


def strip_c(source: str, *, strings: bool = False) -> str:
    def replace(match: re.Match) -> str:
        part = match.group()
        if part.startswith("/"):
            return " " + "\n" * part.count("\n")
        return part if strings else part[0] + part[-1]
    return C_PARTS.sub(replace, source)


def declarations(source: str) -> set[str]:
    """Extract public declaration/macro names from headers or preprocessed C."""
    names: set[str] = set()

    def emit(name: str) -> None:
        if name and not name.startswith("_") and name not in KEYWORDS:
            names.add(name)

    code = strip_c(source)
    for macro in re.findall(r"^\s*#\s*define\s+(" + IDENTIFIER + ")", code, re.M):
        emit(macro)
    code = re.sub(r"^\s*#[^\n]*", "", code, flags=re.M)
    tokens = re.findall(IDENTIFIER + r"|[(){};,=*\[\]]", code)
    top: list[str] = []
    depth = 0
    enum_depth = None
    function_body = False
    previous = before_previous = ""

    def flush() -> None:
        parenthesis = 0
        fn = last = ""
        for index, token in enumerate(top):
            before = top[index - 1] if index else ""
            if token == "(":
                parenthesis += 1
                if parenthesis == 1 and re.fullmatch(IDENTIFIER, before) and before not in KEYWORDS and not before.startswith("__") and not fn:
                    fn = before
            elif token == ")":
                parenthesis -= 1
            elif parenthesis == 1 and before == "(" and token == "*" and index + 1 < len(top):
                last = top[index + 1]
            elif parenthesis == 0 and re.fullmatch(IDENTIFIER, token) and token not in KEYWORDS and not token.startswith("__"):
                last = token
        emit(last if "typedef" in top or not fn else fn)
        top.clear()

    for token in tokens:
        is_identifier = bool(re.fullmatch(IDENTIFIER, token))
        if is_identifier and previous in ("struct", "union", "enum"):
            emit(token)
        if is_identifier and depth == enum_depth and previous in ("{", ","):
            emit(token)
        if token == "{":
            if previous == "enum" or before_previous == "enum":
                enum_depth = depth + 1
            if depth == 0 and previous == ")":
                function_body = True
            depth += 1
        elif token == "}":
            depth -= 1
            if enum_depth is not None and depth < enum_depth:
                enum_depth = None
            if depth == 0 and function_body:
                function_body = False
                flush()
        elif depth == 0:
            if token == ";":
                flush()
            else:
                top.append(token)
        before_previous, previous = previous, token
    return names


def include_list(source: str) -> list[tuple[str, str]]:
    result = []
    for line in strip_c(source, strings=True).splitlines():
        match = re.match(r'^\s*#\s*include\s*(?:<([^>]+)>|"([^"]+)")', line)
        if match:
            result.append(("sys", match[1]) if match[1] else ("usr", match[2]))
    return result


class IncludeAnalysis:
    def __init__(self, session: CheckSession) -> None:
        self.session = session
        self.root = session.ctx.options.directory.resolve()
        self.sources = {path: path.read_text(errors="replace") for path in project_files(
                        self.root, ignore_hidden=session.ctx.options.ignore_hidden)
                        if not path.is_symlink() and path.is_file() and path.suffix in (".c", ".h")}
        self.includes = {path: include_list(source) for path, source in self.sources.items()}
        self.tokens = {path: set(re.findall(IDENTIFIER, re.sub(r"^\s*#\s*include[^\n]*", "", strip_c(source), flags=re.M)))
                       for path, source in self.sources.items()}
        self.system: dict[str, set[str] | None] = {}
        self.provided: dict[Path, set[str]] = {}
        self.reverse: dict[Path, set[Path]] = {}
        for path, includes in self.includes.items():
            for kind, name in includes:
                resolved = self.resolve(path, name) if kind == "usr" else None
                if resolved:
                    self.reverse.setdefault(resolved, set()).add(path)
        self.builtin_macros: set[str] | None = None

    def resolve(self, path: Path, name: str) -> Path | None:
        for candidate in (path.parent / name, self.root / name):
            resolved = candidate.resolve()
            if resolved.is_relative_to(self.root) and resolved in self.sources:
                return resolved
        return None

    def system_names(self, header: str) -> set[str] | None:
        if header not in self.system:
            source = f"#include <{header}>\n"
            status, output = self.session.compiler(source, ("-E", "-P"), name="include-system")
            if status:
                self.system[header] = None
            else:
                if self.builtin_macros is None:
                    _, builtin = self.session.compiler("", ("-E", "-dM"), name="include-builtins")
                    self.builtin_macros = declarations(builtin)
                _, macros = self.session.compiler(source, ("-E", "-dM"), name="include-macros")
                self.system[header] = declarations(output) | (declarations(macros) - self.builtin_macros)
        return self.system[header]

    def provides(self, header: Path) -> set[str]:
        if header not in self.provided:
            visited: set[Path] = set()
            todo = [header]
            names: set[str] = set()
            while todo:
                path = todo.pop()
                if path in visited:
                    continue
                visited.add(path)
                names.update(declarations(self.sources[path]))
                for kind, name in self.includes[path]:
                    if kind == "sys":
                        names.update(self.system_names(name) or ())
                    elif resolved := self.resolve(path, name):
                        todo.append(resolved)
            self.provided[header] = names
        return self.provided[header]

    def users(self, header: Path) -> set[str]:
        visited: set[Path] = set()
        todo = [header]
        used: set[str] = set()
        while todo:
            path = todo.pop()
            if path not in visited:
                visited.add(path)
                used.update(self.tokens[path])
                todo.extend(self.reverse.get(path, ()))
        return used

    def run(self) -> None:
        bad = []
        total = 0
        for path, includes in self.includes.items():
            used = self.users(path) if path.suffix == ".h" else self.tokens[path]
            seen = set()
            covered: set[str] = set()
            for kind, name in includes:
                total += 1
                label = f"<{name}>" if kind == "sys" else f'"{name}"'
                prefix = f"{path.relative_to(self.root)}: {label}"
                if (kind, name) in seen:
                    bad.append(prefix + self.session.text(" included twice", " inclus deux fois"))
                    continue
                seen.add((kind, name))
                if kind == "sys":
                    provided = self.system_names(name)
                    if provided is None:
                        continue
                else:
                    resolved = self.resolve(path, name)
                    if not resolved:
                        continue
                    provided = self.provides(resolved)
                hit = used & provided
                common = hit & COMMON
                if hit - COMMON or common - covered:
                    covered.update(common)
                elif common:
                    bad.append(prefix + self.session.text(" only repeats common types/macros", " répète seulement des types/macros communs"))
                else:
                    bad.append(prefix + self.session.text(" unused", " inutilisé"))
        self.session.check("SKIP" if not total else "KO" if bad else "OK", "Includes", "Includes",
                           f"{len(bad)}/{total} unused or duplicate includes" if bad else f"{total} includes used",
                           f"{len(bad)}/{total} includes inutiles ou dupliqués" if bad else f"{total} includes utilisés")
        self.session.details(bad)
