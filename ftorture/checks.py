"""Native subject-check reports and compiler/tool probes."""
from pathlib import Path

from .runtime import Context


class CheckReport:
    """Write engine check records for a new project's native Python checks.

    Values are single-line fields: pipes/newlines are data, not extra records.
    Collect in memory, then replace checks.txt once validation has finished.
    """

    def __init__(self) -> None:
        self.records: list[str] = []

    def _add(self, *fields: str) -> None:
        self.records.append("|".join(str(value).replace("|", "/").replace("\r", " ").replace("\n", " ")
                                     for value in fields))

    def section(self, title: str) -> None:
        self._add("S", title)

    def check(self, status: str, label: str, detail: str = "") -> None:
        if status not in ("OK", "KO", "WARN", "SKIP"):
            raise ValueError(f"Unknown check status: {status}")
        self._add("C", status, label, detail)

    def detail(self, value: str) -> None:
        self._add("D", value)

    def prototype(self, name: str, status: str, expected: str, found: str) -> None:
        if status not in ("OK", "KO", "WARN"):
            raise ValueError(f"Unknown prototype status: {status}")
        self._add("P", name, status, expected, found)

    def end_prototypes(self) -> None:
        self._add("PS")

    def write(self, path: Path) -> None:
        path.write_text("\n".join(self.records) + "\n", encoding="utf-8")


class CheckSession:
    """One check run: localized records and inspectable probe diagnostics."""

    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx
        self.report = CheckReport()
        self.directory = ctx.build / "checks"
        self.directory.mkdir(exist_ok=True)
        self.sequence = 0

    def text(self, en: str, fr: str) -> str:
        return self.ctx.message(en, fr)

    def capture(self, args: list[str | Path], *, cwd: Path | None = None,
                name: str = "probe") -> tuple[int, str]:
        self.sequence += 1
        log = self.directory / f"{self.sequence:03d}-{name}.log"
        status = self.ctx.command(args, log=log, cwd=cwd)
        return status, log.read_text(errors="replace")

    def compiler(self, source: str, flags: tuple[str, ...] = ("-fsyntax-only",),
                 *, name: str = "compiler") -> tuple[int, str]:
        path = self.directory / f"{name}.c"
        path.write_text(source, encoding="utf-8")
        return self.capture([*self.ctx.cc, "-std=gnu11", f"-I{self.ctx.options.directory}",
                             *flags, "-x", "c", path], name=name)

    def check(self, status: str, en_label: str, fr_label: str,
              en_detail: str = "", fr_detail: str = "") -> None:
        self.report.check(status, self.text(en_label, fr_label), self.text(en_detail, fr_detail))

    def details(self, values: list[str], limit: int = 12) -> None:
        for value in values[:limit]:
            self.report.detail(value)
        if len(values) > limit:
            self.report.detail(self.text(f"… {len(values) - limit} more", f"… {len(values) - limit} autres"))
