"""Unified Python presentation, aggregation, and logging backend for all projects."""
from dataclasses import dataclass
import math
from pathlib import Path

from .explain import build_repro_command, explain_failure, localize_name, read_test_source
from .language import text
from .runtime import Options
from .ui import ANSI_RE, Terminal


@dataclass
class PartStats:
    part: int
    short_name: str
    suites_ok: int = 0
    suites_total: int = 0


def _vis_len(value: str) -> int:
    return len(ANSI_RE.sub("", value))


def _padv(value: str, width: int) -> str:
    return value + (" " * max(0, width - _vis_len(value)))


class Renderer:
    """Single presentation & report backend shared by C, Python, and custom suites."""

    def __init__(self, options: Options, log_path: Path, repro_prefix: str = "") -> None:
        self.options = options
        self.log_path = log_path
        self.repro_prefix = repro_prefix
        self.terminal = Terminal(options.lang, options.no_color)
        self.log_lines: list[str] = []
        self.checks_rendered = False
        self.legend_shown = False
        self.seen_parts: set[tuple[int, str]] = set()
        self.parts: dict[int, PartStats] = {}
        self.notes: list[str] = []

        # Aggregated check counters
        self.checks_ok = 0
        self.checks_ko = 0
        self.checks_warn = 0
        self.proto_ok = 0
        self.proto_tot = 0

        # Aggregated test counters
        self.total_pass = 0
        self.total_fail = 0
        self.total_spec = 0
        self.total_crash_eq = 0
        self.total_tests = 0
        self.total_missing = 0

        # Efficiency tracking (-e)
        self.benches: list[dict] = []
        self.hw: dict | None = None

        # Live C-suite streaming state
        self._col = 0
        self._cur_events: list[dict] = []
        self._cur_label = ""
        self._max_details = 3

    def t(self, en: str, fr: str) -> str:
        return text(self.options.lang, en, fr)

    def _amber(self) -> str:
        return self.terminal.escape("38;5;221")

    def _cyan(self) -> str:
        return self.terminal.escape("38;5;80")

    def _grey(self) -> str:
        return self.terminal.escape("38;5;244")

    def _eff_color(self, pct: int) -> str:
        if pct >= self.options.efficiency_target:
            return self.terminal.ph
        if pct * 2 >= self.options.efficiency_target:
            return self._amber()
        return self.terminal.red

    def add_note(self, note: str) -> None:
        if note and note not in self.notes:
            self.notes.append(note)

    def render_checks(self, checks_file: Path) -> None:
        if self.checks_rendered or not self.options.checks or not checks_file.is_file():
            return
        self.checks_rendered = True
        term = self.terminal
        amber, grey = self._amber(), self._grey()
        proto_buf: list[str] = []

        def flush_protos() -> None:
            if proto_buf:
                term.write("".join(proto_buf))
                proto_buf.clear()

        for raw in checks_file.read_text(encoding="utf-8", errors="replace").splitlines():
            parts = raw.split("|")
            if not parts:
                continue
            kind = parts[0]
            if kind == "S" and len(parts) >= 2:
                flush_protos()
                title = parts[1]
                term.section_bar(title)
                self.log_lines.append(f"\n== {title} ==")
            elif kind == "C" and len(parts) >= 4:
                st, label, detail = parts[1], parts[2], "|".join(parts[3:])
                if st == "OK":
                    mk, col = "✔", term.ph
                    self.checks_ok += 1
                elif st == "KO":
                    mk, col = "✘", term.red
                    self.checks_ko += 1
                elif st == "WARN":
                    mk, col = "▲", amber
                    self.checks_warn += 1
                else:
                    mk, col = "·", grey
                det_col = grey if st == "OK" else ""
                term.write(f"   {col}{mk}{term.reset} {_padv(label, 24)} {det_col}{detail}{term.reset}\n")
                self.log_lines.append(f"[{st}] {label} : {detail}" if detail else f"[{st}] {label}")
            elif kind == "D" and len(parts) >= 2:
                text_val = "|".join(parts[1:])
                term.write(f"       {grey}{text_val}{term.reset}\n")
                self.log_lines.append(f"       {text_val}")
            elif kind == "P" and len(parts) >= 5:
                name, st, exp, found = parts[1], parts[2], parts[3], "|".join(parts[4:])
                self.proto_tot += 1
                if st == "OK":
                    self.proto_ok += 1
                    continue
                mk, col = ("✘", term.red) if st == "KO" else ("▲", amber)
                found_disp = found or self.t("(not declared in header)", "(non déclaré dans le header)")
                proto_buf.append(
                    f"   {col}{mk}{term.reset} {term.bold}{name}{term.reset}\n"
                    f"       {grey}{self.t('expected', 'attendu ')}{term.reset} {term.ph}{exp}{term.reset}\n"
                    f"       {grey}{self.t('found   ', 'trouvé  ')}{term.reset} {col}{found_disp}{term.reset}\n"
                )
                self.log_lines.append(
                    f"[PROTO {st}] {name}\n"
                    f"   {self.t('expected:', 'attendu :')} {exp}\n"
                    f"   {self.t('found   :', 'trouvé  :')} {found_disp}"
                )
            elif kind == "PS":
                bad = self.proto_tot - self.proto_ok
                col = term.red if bad else term.ph
                mk = "✘" if bad else "✔"
                det_col = term.red if bad else grey
                label_txt = self.t(f"{self.proto_ok}/{self.proto_tot} matching",
                                   f"{self.proto_ok}/{self.proto_tot} conformes")
                term.write(f"   {col}{mk}{term.reset} {_padv('Prototypes', 24)} {det_col}{label_txt}{term.reset}\n")
                if bad:
                    self.checks_ko += 1
                else:
                    self.checks_ok += 1
                flush_protos()
        flush_protos()

    def render_legend(self, *, c_mode: bool = True) -> None:
        if self.legend_shown:
            return
        self.legend_shown = True
        term = self.terminal
        amber, cyan, grey = self._amber(), self._cyan(), self._grey()
        if c_mode:
            term.write(
                f"\n   {grey}{self.t('Legend', 'Légende')}{term.reset}  "
                f"{term.ph}✔{term.reset} ok   "
                f"{cyan}✔{term.reset} {self.t('same crash as libc', 'crash identique à la libc')}   "
                f"{term.red}✘{term.reset} {self.t('error', 'erreur')}   "
                f"{term.red}S{term.reset} crash\n"
                f"            {term.red}T{term.reset} timeout   "
                f"{term.red}L{term.reset} {self.t('leak', 'fuite')}   "
                f"{term.red}M{term.reset} {self.t('malloc protection', 'protection malloc')}   "
                f"{amber}▲{term.reset} {self.t('speculative', 'spéculatif')}\n"
            )
        else:
            term.write(
                f"\n   {grey}{self.t('Legend', 'Légende')}{term.reset}  "
                f"{term.ph}✔{term.reset} ok   "
                f"{term.red}✘{term.reset} {self.t('error', 'erreur')}   "
                f"{term.red}T{term.reset} timeout   "
                f"{amber}▲{term.reset} {self.t('speculative', 'spéculatif')}\n"
            )

    def render_part(self, part: int, title: str, short_name: str) -> None:
        if part not in self.parts:
            self.parts[part] = PartStats(part, short_name)
        key = (part, title)
        if key not in self.seen_parts:
            self.seen_parts.add(key)
            self.terminal.section_bar(title)
            self.log_lines.append(f"\n===== {title} =====")

    def print_eff_badge(self, eff: dict) -> None:
        term = self.terminal
        pct = int(eff.get("pct", -1))
        if pct < 0:
            return
        bound = "<" if eff.get("bound") else ""
        col = self._eff_color(pct)
        term.write(f"  {col}⚡ {bound}{pct}%{term.reset}")
        label = eff.get("label", "")
        ideal = float(eff.get("ideal", 0.0))
        real = float(eff.get("real", 0.0))
        if eff.get("score"):
            self.log_lines.append(
                f"   eff {label} : {bound}{pct}% ({self.t('target', 'objectif')} {self.options.efficiency_target}%, "
                f"{self.t('reference', 'référence')} {ideal:.0f}, {self.t('yours', 'toi')} {real:.0f})"
            )
        else:
            self.log_lines.append(
                f"   eff {label} : {bound}{pct}% ({self.t('target', 'objectif')} {self.options.efficiency_target}%, "
                f"{self.t('ideal', 'parfait')} {ideal * 1e6:.2f} µs, {self.t('yours', 'toi')} {'>' if bound else ''}{real * 1e6:.2f} µs)"
            )

    def _format_c_failure(self, ev: dict) -> tuple[str, str, str, str]:
        """Return (compact_term, verbose_term, plain_summary, plain_verbose)."""
        term = self.terminal
        amber, grey = self._amber(), self._grey()
        res = int(ev["res"])
        glyph = str(ev["glyph"])
        idx = int(ev.get("index", 0))
        name = localize_name(str(ev.get("name", "")), self.options.lang)
        file_path = str(ev.get("file", ""))
        base = Path(file_path).name if file_path else ""
        line = int(ev.get("line", 0))
        msg = str(ev.get("msg", ""))
        inp = str(ev.get("input", ""))
        exp = str(ev.get("expected", ""))
        act = str(ev.get("actual", ""))
        why = str(ev.get("why", ""))
        sig = int(ev.get("sig", 0))
        col = amber if res == 3 else term.red

        loc = f"  {base}:{line}" if base and line else ""
        head_t = f"      {col}{glyph}{term.reset} #{idx} « {name} »{grey}{loc}{term.reset}\n"
        head_p = f"      {glyph} #{idx} « {name} »{loc}\n"
        body_t = [head_t]
        body_p = [head_p]
        if inp:
            lbl = self.t("input   ", "entrée  ")
            body_t.append(f"         {grey}{lbl}{term.reset} {inp}\n")
            body_p.append(f"         {lbl} {inp}\n")
        if msg:
            body_t.append(f"         {col}{msg}{term.reset}\n")
            body_p.append(f"         {msg}\n")
        if exp:
            lbl = self.t("expected", "attendu ")
            body_t.append(f"         {grey}{lbl}{term.reset} {term.ph}{exp}{term.reset}\n")
            body_p.append(f"         {lbl} {exp}\n")
        if act:
            lbl = self.t("actual  ", "obtenu  ")
            body_t.append(f"         {grey}{lbl}{term.reset} {col}{act}{term.reset}\n")
            body_p.append(f"         {lbl} {act}\n")

        verb_t: list[str] = []
        verb_p: list[str] = []
        reason = explain_failure(why, sig=sig, msg=msg, lang=self.options.lang)
        if reason:
            lbl = self.t("why     ", "pourquoi")
            verb_t.append(f"         {grey}{lbl}{term.reset} {reason}\n")
            verb_p.append(f"         {lbl} {reason}\n")
        src_lines = read_test_source(file_path, int(ev.get("test_line", 0) or line))
        if src_lines:
            lbl = self.t("test    ", "test    ")
            verb_t.append(f"         {grey}{lbl} {base}:{ev.get('test_line') or line}{term.reset}\n")
            verb_p.append(f"         {lbl} {base}:{ev.get('test_line') or line}\n")
            for sl in src_lines:
                verb_t.append(f"           {grey}│{term.reset} {sl}\n")
                verb_p.append(f"           │ {sl}\n")
        repro = build_repro_command(
            self.repro_prefix, file_path=file_path, idx=int(ev.get("tidx", -1)),
            fail_at=int(ev.get("fail_at", 0)), suite=str(ev.get("suite", "")),
            z_bs=ev.get("z_bs"),
        )
        if repro:
            lbl = self.t("replay  ", "rejouer ")
            verb_t.append(f"         {grey}{lbl}{term.reset} {term.ph}{repro}{term.reset}\n")
            verb_p.append(f"         {lbl} {repro}\n")

        return "".join(body_t), "".join(verb_t), "".join(body_p), "".join(verb_p)

    def consume_c_event(self, event: dict) -> None:
        kind = event.get("type")
        term = self.terminal
        amber, cyan, grey = self._amber(), self._cyan(), self._grey()

        if kind == "part":
            self.render_legend(c_mode=True)
            self.render_part(int(event["part"]), str(event["title"]), str(event["short"]))
            return

        if kind == "suite_start":
            self.render_legend(c_mode=True)
            part = int(event["part"])
            if part not in self.parts:
                self.parts[part] = PartStats(part, str(event.get("short", f"part {part}")))
            label = str(event["label"])
            self._cur_label = label
            self._cur_events = []
            term.write(f"   {term.bold}{_padv(label, 16)}{term.reset} ")
            if event.get("missing"):
                archive = str(event.get("archive", ""))
                total = int(event.get("total", 0))
                self.total_missing += 1
                self.parts[part].suites_total += 1
                msg = self.t(f"✘ MISSING from {archive}", f"✘ ABSENTE de {archive}")
                skip = self.t(f"({total} tests skipped)", f"({total} tests ignorés)")
                term.write(f"{term.red}{term.bold}{msg}{term.reset} {grey}{skip}{term.reset}\n")
                self.log_lines.append(f"\n{label} : {self.t('MISSING', 'ABSENTE')}")
            else:
                self._col = 21
            return

        if kind == "test":
            res = int(event["res"])
            glyph = str(event["glyph"])
            gc = term.ph if res == 0 else cyan if res == 1 else amber if res == 3 else term.red
            width = term.inner_width() + 6
            if self._col + 2 > width - 10:
                term.write("\n" + (" " * 21))
                self._col = 21
            term.write(f"{gc}{glyph}{term.reset} ")
            self._col += 2
            if res in (2, 3):
                self._cur_events.append(event)
            return

        if kind == "suite_end":
            if event.get("missing"):
                return
            part = int(event["part"])
            ps = self.parts.setdefault(part, PartStats(part, f"part {part}"))
            s_pass = int(event["pass"])
            s_fail = int(event["fail"])
            s_spec = int(event["spec"])
            s_crash_eq = int(event.get("crash_eq", 0))
            s_total = int(event["total"])
            self.total_pass += s_pass
            self.total_fail += s_fail
            self.total_spec += s_spec
            self.total_crash_eq += s_crash_eq
            self.total_tests += s_total
            ps.suites_total += 1
            bad_suite = s_fail or (self.options.speculative and s_spec)
            if not bad_suite:
                ps.suites_ok += 1

            cnt_col = term.red if bad_suite else amber if s_spec else term.ph
            term.write(f" {term.bold}{cnt_col}{s_pass}/{s_total}{term.reset}")
            if s_spec:
                term.write(f" {amber}({s_spec} ▲){term.reset}")
            eff = event.get("eff")
            if isinstance(eff, dict):
                self.benches.append(eff)
                self.print_eff_badge(eff)
            term.write("\n")

            self.log_lines.append(
                f"\n{self._cur_label} : {s_pass}/{s_total} ({s_spec} {self.t('speculative', 'spéculatif')})"
            )
            shown = 0
            for ev in self._cur_events:
                res = int(ev["res"])
                compact_t, verbose_t, plain_s, plain_v = self._format_c_failure(ev)
                self.log_lines.append(plain_s.rstrip("\n"))
                if plain_v:
                    self.log_lines.append(plain_v.rstrip("\n"))
                if self.options.verbose or (shown < self._max_details and (res == 2 or self.options.speculative)):
                    term.write(compact_t)
                    if verbose_t and self.options.verbose:
                        term.write(verbose_t)
                    shown += 1
                elif res == 3 and shown < self._max_details + 2:
                    first_line = compact_t.splitlines()[0] if compact_t.splitlines() else ""
                    if first_line:
                        term.write(first_line + "\n")
                    shown += 1
            if len(self._cur_events) > shown:
                more = len(self._cur_events) - shown
                msg = self.t(
                    f"… {more} more details: rerun with -v or see {self.log_path}",
                    f"… {more} autre(s) détail(s) : relance avec -v ou regarde {self.log_path}",
                )
                term.write(f"      {grey}{msg}{term.reset}\n")
            return

        if kind == "bench":
            self.benches.append(event)
            label = str(event.get("label", ""))
            term.write(f"\n   {term.bold}{_padv(label, 16)}{term.reset}")
            self.print_eff_badge(event)
            term.write("\n")
            return

        if kind == "hw":
            self.hw = event
            return

    def record_suite(self, *, part: int, short_name: str, label: str,
                     outcomes: list[tuple[str, str, str, bool, str, str, str]],
                     missing_msg: str = "", label_width: int = 30,
                     eff: dict | None = None) -> None:
        """Record & render one Python/push_swap/custom suite."""
        term = self.terminal
        amber, grey = self._amber(), self._grey()
        ps = self.parts.setdefault(part, PartStats(part, short_name))
        ps.suites_total += 1
        if missing_msg:
            self.total_missing += 1
            term.write(f"   {term.bold}{_padv(label, label_width)}{term.reset} {term.red}✘ {missing_msg}{term.reset}\n")
            self.log_lines.append(f"[✘] {label}: {missing_msg}")
            return

        s_pass = s_fail = s_spec = 0
        marks: list[str] = []
        failures: list[tuple[str, str, str, str, str, str]] = []
        for sym, test_label, detail, is_spec, inp, exp, act in outcomes:
            if sym == "✔":
                s_pass += 1
                marks.append(f"{term.ph}✔{term.reset}")
                self.log_lines.append(f"  [✔] {label}: {test_label}")
            elif sym == "▲":
                s_spec += 1
                marks.append(f"{amber}▲{term.reset}")
                failures.append((sym, test_label, detail, inp, exp, act))
                self.log_lines.append(f"  [▲] {label}: {test_label}" + (f" — {detail}" if detail else ""))
            else:
                s_fail += 1
                marks.append(f"{term.red}{sym}{term.reset}")
                failures.append((sym, test_label, detail, inp, exp, act))
                self.log_lines.append(f"  [{sym}] {label}: {test_label}" + (f" — {detail}" if detail else ""))

        s_total = len(outcomes)
        self.total_pass += s_pass
        self.total_fail += s_fail
        self.total_spec += s_spec
        self.total_tests += s_total
        bad_suite = s_fail or (self.options.speculative and s_spec)
        if not bad_suite:
            ps.suites_ok += 1

        cnt_col = term.red if bad_suite else amber if s_spec else term.ph
        spec_note = f" {amber}({s_spec} ▲){term.reset}" if s_spec else ""
        term.write(
            f"   {term.bold}{_padv(label, label_width)}{term.reset} "
            f"{' '.join(marks)}  {term.bold}{cnt_col}{s_pass}/{s_total}{term.reset}{spec_note}"
        )
        if isinstance(eff, dict) and int(eff.get("pct", -1)) >= 0:
            self.benches.append(eff)
            self.print_eff_badge(eff)
        term.write("\n")

        shown = 0
        for sym, test_label, detail, inp, exp, act in failures:
            if inp:
                self.log_lines.append(f"      input:    {inp}")
            if exp:
                self.log_lines.append(f"      expected: {exp}")
            if act:
                self.log_lines.append(f"      actual:   {act}")
            is_fail = sym != "▲"
            if self.options.verbose or (shown < self._max_details and (is_fail or self.options.speculative)):
                c = amber if sym == "▲" else term.red
                term.write(f"       {c}{sym}{term.reset} {test_label}")
                if detail:
                    term.write(f" — {grey}{detail}{term.reset}")
                term.write("\n")
                if inp:
                    term.write(f"         {grey}input   :{term.reset} {inp}\n")
                if exp:
                    term.write(f"         {grey}expected:{term.reset} {exp}\n")
                if act:
                    term.write(f"         {grey}actual  :{term.reset} {act}\n")
                shown += 1
            elif sym == "▲" and shown < self._max_details + 2:
                term.write(f"       {amber}▲{term.reset} {test_label}\n")
                shown += 1

    def _eff_summary_lines(self) -> list[str]:
        if not self.options.efficiency and not self.benches:
            return []
        term = self.terminal
        amber, grey = self._amber(), self._grey()
        measured = [b for b in self.benches if int(b.get("pct", -1)) >= 0]
        lines = [""]
        if not measured:
            lines.append(
                f"{term.dark}{self.t('EFFICIENCY', 'EFFICACITÉ')}{term.reset} "
                f"{grey}{self.t('no measurement', 'aucune mesure')}{term.reset}"
            )
            return lines

        gmean = sum(math.log(max(1, min(200, int(b["pct"])))) for b in measured) / len(measured)
        pct = int(math.exp(gmean) + 0.5)
        target = self.options.efficiency_target
        target_lbl = self.t(f"target {target}%", f"objectif {target}%")
        bw = max(6, term.inner_width() - 2 - 28 - len(target_lbl))
        filled = min(100, pct) * bw // 100
        mark_pos = min(bw - 1, target * bw // 100)
        eff_col = self._eff_color(pct)
        gauge = "".join(
            f"{amber}{'▓' if idx < filled else '┃'}{term.reset}" if idx == mark_pos
            else (f"{eff_col}█{term.reset}" if idx < filled else f"{term.dark}░{term.reset}")
            for idx in range(bw)
        )
        lines.append(
            f"{term.ph}{self.t('EFFICIENCY', 'EFFICACITÉ')}{term.reset}         "
            f"{term.dark}▕{gauge}{term.dark}▏{term.reset} "
            f"{eff_col}{pct:3d}%{term.reset}  {amber}{target_lbl}{term.reset}"
        )

        below = sorted((b for b in measured if int(b["pct"]) < target), key=lambda b: int(b["pct"]))
        if below:
            room = term.inner_width() - 2 - 22
            slow_str = ""
            for i, b in enumerate(below):
                bpct = int(b["pct"])
                bound = "<" if b.get("bound") else ""
                item = f"{' · ' if i else ''}{term.bold}{b['label']}{self._eff_color(bpct)} {bound}{bpct}%{term.reset}"
                if _vis_len(slow_str) + _vis_len(item) + (2 if i + 1 < len(below) else 0) > room:
                    if i:
                        slow_str += " …"
                    break
                slow_str += item
            lines.append(f"{term.dark}{self.t('  below target:', '  sous l\'objectif :')}{term.reset} {slow_str}")
        else:
            lines.append(
                f"{term.ph}  {len(measured)}/{len(measured)} "
                f"{self.t('measurement(s) above target', 'mesure(s) au-dessus de l\'objectif')}{term.reset}"
            )

        if self.hw and any(not b.get("score") for b in measured):
            hw = self.hw
            lines.append(
                f"{term.dark}"
                + self.t(
                    f"  costs measured here: byte {hw['scan']*1e9:.1f} ns · "
                    f"malloc {hw['allocs']*1e9:.0f} ns · syscall {hw['sys']*1e9:.0f} ns",
                    f"  coûts mesurés ici : octet {hw['scan']*1e9:.1f} ns · "
                    f"malloc {hw['allocs']*1e9:.0f} ns · syscall {hw['sys']*1e9:.0f} ns",
                )
                + term.reset
            )
            self.log_lines.append(
                self.t(
                    f"machine: loop turn {hw['iters']*1e9:.2f} ns, byte scanned {hw['scan']*1e9:.2f} ns, "
                    f"copied {hw['copy']*1e9:.2f} ns, stored {hw['store']*1e9:.2f} ns, "
                    f"compared {hw['cmp']*1e9:.2f} ns, malloc {hw['allocs']*1e9:.1f} ns, "
                    f"syscall {hw['sys']*1e9:.0f} ns",
                    f"machine : tour de boucle {hw['iters']*1e9:.2f} ns, octet lu {hw['scan']*1e9:.2f} ns, "
                    f"copié {hw['copy']*1e9:.2f} ns, écrit {hw['store']*1e9:.2f} ns, "
                    f"comparé {hw['cmp']*1e9:.2f} ns, malloc {hw['allocs']*1e9:.1f} ns, "
                    f"syscall {hw['sys']*1e9:.0f} ns",
                )
            )
        self.log_lines.append(
            self.t(
                f"EFFICIENCY: {pct}% (target {target}%, {len(measured)} measurement(s), {len(below)} below target)",
                f"EFFICACITÉ : {pct}% (objectif {target}%, {len(measured)} mesure(s), {len(below)} sous l'objectif)",
            )
        )
        return lines

    def finish(self, *, item_en: str = "functions", item_fr: str = "fonctions",
               include_checks: bool = True, extra_failed: bool = False) -> int:
        term = self.terminal
        amber, cyan = self._amber(), self._cyan()

        stats: list[str] = []
        fok = fall = 0
        for part_num in sorted(self.parts):
            ps = self.parts[part_num]
            if not ps.suites_total:
                continue
            fok += ps.suites_ok
            fall += ps.suites_total
            stats.append(term.progress_row(ps.part, ps.short_name, ps.suites_ok, ps.suites_total))
        for note in self.notes:
            stats.append(f"{amber}{note}{term.reset}")
        if stats:
            stats.append("")

        stats.append(
            f"{term.dark}TESTS {term.reset} "
            f"{term.ph}{self.total_pass} ✔{term.reset}  "
            f"{term.red if self.total_fail else term.dark}{self.total_fail} ✘{term.reset}  "
            f"{amber if self.total_spec else term.dark}{self.total_spec} ▲{term.reset}  "
            f"{term.dark}/ {self.total_tests}{term.reset}"
        )
        if self.total_crash_eq:
            stats.append(
                f"{cyan}       "
                + self.t(
                    f"including {self.total_crash_eq} libc-matching crashes (accepted)",
                    f"dont {self.total_crash_eq} crash identique(s) à la libc (acceptés)",
                )
                + term.reset
            )
        if self.total_missing:
            stats.append(
                f"{term.dark}{self.t('MISSING', 'ABSENT ')}{term.reset} "
                f"{term.red}{self.total_missing} {self.t(item_en, item_fr)}{term.reset}"
            )
        if include_checks and (self.options.checks or self.checks_ok or self.checks_ko or self.proto_tot):
            proto_str = ""
            if self.proto_tot:
                pcol = term.ph if self.proto_ok == self.proto_tot else term.red
                proto_str = f"  {pcol}protos {self.proto_ok}/{self.proto_tot}{term.reset}"
            stats.append(
                f"{term.dark}CHECKS{term.reset} "
                f"{term.ph}{self.checks_ok} ✔{term.reset}  "
                f"{term.red if self.checks_ko else term.dark}{self.checks_ko} ✘{term.reset}  "
                f"{amber if self.checks_warn else term.dark}{self.checks_warn} ▲{term.reset}"
                f"{proto_str}"
            )

        stats.extend(self._eff_summary_lines())

        bad_checks = self.checks_ko + (self.checks_warn if self.options.speculative else 0)
        bad_tests = self.total_fail + self.total_missing + (self.total_spec if self.options.speculative else 0)
        bad = bad_checks + bad_tests + (1 if extra_failed and not bad_tests else 0)

        headline = (
            self.t(f"{fok}/{fall} perfect {item_en} · no errors",
                   f"{fok}/{fall} {item_fr} parfaites · aucune erreur")
            if not bad else
            self.t(f"{bad} problems · {fok}/{fall} {item_en} OK",
                   f"{bad} problème(s) · {fok}/{fall} {item_fr} OK")
        )
        warn_total = self.total_spec + (self.checks_warn if include_checks else 0)
        warnings = (
            self.t(f"{warn_total} speculative ▲ warnings to review",
                   f"{warn_total} avertissement(s) ▲ à savoir défendre")
            if not self.options.speculative and warn_total else ""
        )

        verdict = "KO" if bad else "OK"
        self.log_lines.append(
            self.t(
                f"\nTOTAL: {self.total_pass} ok, {self.total_fail} failed, "
                f"{self.total_spec} speculative, {self.total_missing} missing, "
                f"{self.checks_ko} failed checks -> {verdict}\n",
                f"\nTOTAL: {self.total_pass} ok, {self.total_fail} ko, "
                f"{self.total_spec} spéculatifs, {self.total_missing} absentes, "
                f"{self.checks_ko} vérifs KO -> {verdict}\n",
            )
        )
        self.log_path.write_text("\n".join(self.log_lines), encoding="utf-8")
        term.result_box(ok=not bad, stats=stats, headline=headline, warnings=warnings, log_path=self.log_path)
        return 1 if bad else 0
