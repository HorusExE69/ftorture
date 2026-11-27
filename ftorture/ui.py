"""Original phosphor-green TUI, implemented with the Linux standard library."""
from contextlib import contextmanager
from dataclasses import replace
import glob
import os
from pathlib import Path
import re
import readline
import select
import shutil
import sys
import termios
import tty

from .language import text
from .registry import Registry
from .runtime import Options

ANSI_RE = re.compile(r"\033\[[0-?]*[ -/]*[@-~]")

FONT = {
    "F": "###:#..:##.:#..:#..", "T": "###:.#.:.#.:.#.:.#.",
    "O": "###:#.#:#.#:#.#:###", "R": "##.:#.#:##.:#.#:#.#",
    "U": "#.#:#.#:#.#:#.#:###", "E": "###:#..:##.:#..:###",
    "K": "#.#:#.#:##.:#.#:#.#",
}


class Terminal:
    def __init__(self, lang: str, no_color: bool = False):
        self.lang = lang
        self.color = sys.stdout.isatty() and not no_color and not os.environ.get("NO_COLOR")
        self.ph = self.escape("38;5;46")
        self.medium = self.escape("38;5;34")
        self.dark = self.escape("38;5;22")
        self.bold = self.escape("1")
        self.reset = self.escape("0")
        self.red = self.escape("38;5;203")
        self.inverse = self.escape("48;5;46;38;5;16;1")

    def escape(self, code: str) -> str:
        return f"\033[{code}m" if self.color else ""

    def t(self, en: str, fr: str) -> str:
        return text(self.lang, en, fr)

    def write(self, value: str) -> None:
        print(value, end="", flush=True)

    def clear(self) -> None:
        if sys.stdout.isatty():
            self.write("\033[H\033[2J\033[3J")

    def cursor(self, visible: bool) -> None:
        if sys.stdout.isatty():
            self.write("\033[?25h" if visible else "\033[?25l")

    def banner(self, project=None) -> None:
        grid = {(r, i * 4 + c) for i, letter in enumerate("FTORTURE")
                for r, row in enumerate(FONT[letter].split(":"))
                for c, pixel in enumerate(row) if pixel == "#"}
        self.write("\n")
        for r, scan in enumerate((46, 40, 46, 40, 46, 22)):
            line = "   "
            for c in range(32):
                if (r, c) in grid:
                    line += self.escape(f"38;5;{scan}") + "██"
                elif (r - 1, c - 1) in grid:
                    line += self.dark + "▒▒"
                else:
                    line += "  "
            self.write(line + self.reset + "\n")
        subtitle = "42 TESTER · LIBFT · FT_PRINTF · GET_NEXT_LINE · PUSH_SWAP · PYTHON"
        tag = self.t("> your code will talk", "> ton code va parler")
        if project:
            subtitle = f"{project.name.upper()} · {self.t('SUBJECT', 'SUJET')} v{project.subject} · LINUX"
            if project.custom:
                subtitle = f"[CUSTOM] {project.name}"
            tags = {"libft": ("> your libft will talk", "> ta libft va parler"),
                    "printf": ("> your printf will talk", "> ton printf va parler"),
                    "gnl": ("> your gnl will talk", "> ta gnl va parler"),
                    "push_swap": ("> your push_swap will talk", "> ton push_swap va parler"),
                    "py00": ("> your python will talk", "> ton python va parler"),
                    "py01": ("> your python will talk", "> ton python va parler"),
                    "py02": ("> your python will talk", "> ton python va parler")}
            tag = self.t(*tags.get(project.key, ("> your code will talk", "> ton code va parler")))
        self.write(f"   {self.medium}▚▚ {subtitle} ▞▞{self.reset}\n")
        self.write(f"   {self.ph}{tag}{self.reset}{self.escape('5')}{self.ph}_{self.reset}\n\n")

    def heading(self, en: str, fr: str, project=None) -> None:
        self.clear()
        self.banner(project)
        self.write(f"   {self.bold}{self.ph}{self.t(en, fr)}{self.reset}\n\n")

    def inner_width(self) -> int:
        return max(44, min(shutil.get_terminal_size((82, 24)).columns - 6, 76))

    def section_bar(self, title: str) -> None:
        width = max(4, self.inner_width() - 4 - len(title))
        self.write(f"\n    {self.ph}▶ {self.bold}{title}{self.reset}  {self.dark}{'▀' * width}{self.reset}\n\n")

    def progress_row(self, part: int, label: str, ok: int, total: int) -> str:
        bw = max(6, self.inner_width() - 2 - 34)
        filled = (ok * bw // total) if total else 0
        bar_color = self.ph if ok == total else self.escape("38;5;221") if ok * 2 >= total else self.red
        meter = f"{bar_color}{'█' * filled}{self.dark}{'░' * (bw - filled)}{self.reset}"
        count_color = self.ph if ok == total else self.red
        pct = (ok * 100 // total) if total else 0
        return (f"{self.ph}P{part}{self.reset} {label:<16} "
                f"{self.dark}▕{meter}{self.dark}▏{self.reset} "
                f"{count_color}{ok:2d}/{total:<2d}{self.reset}  {pct:3d}%")

    def pixel_rows(self, word: str, colors: tuple[int, ...], shadow: int) -> list[str]:
        grid = {(r, i * 4 + c) for i, letter in enumerate(word)
                for r, row in enumerate(FONT[letter].split(":"))
                for c, pixel in enumerate(row) if pixel == "#"}
        width = len(word) * 4
        shadow_esc = self.escape(f"38;5;{shadow}")
        rows = []
        for r in range(6):
            fg = self.escape(f"38;5;{colors[r]}")
            line = ""
            for c in range(width):
                if (r, c) in grid:
                    line += fg + "██"
                elif (r - 1, c - 1) in grid:
                    line += shadow_esc + "▒▒"
                else:
                    line += "  "
            rows.append(line + self.reset)
        return rows

    def result_box(self, *, ok: bool, stats: list[str], headline: str,
                   warnings: str = "", log_path: Path | None = None) -> None:
        inner = self.inner_width()
        title = self.t("RESULT", "RÉSULTAT")
        top_fill = max(0, inner - 5 - len(title))
        self.write(f"\n   {self.medium}█▀▀▀{self.inverse} {title} {self.reset}{self.medium}{'▀' * top_fill}█{self.reset}\n")

        def vis_len(value: str) -> int:
            return len(ANSI_RE.sub("", value))

        def box_line(content: str = "") -> None:
            pad = max(0, inner - 1 - vis_len(content))
            self.write(f"   {self.medium}█{self.reset} {content}{' ' * pad}{self.medium}█{self.reset}\n")

        def box_center(content: str) -> None:
            width = vis_len(content)
            left = max(0, (inner - width) // 2)
            right = max(0, inner - left - width)
            self.write(f"   {self.medium}█{self.reset}{' ' * left}{content}{' ' * right}{self.medium}█{self.reset}\n")

        box_line()
        for row in stats:
            box_line(row)
        box_line()
        word = "OK" if ok else "KO"
        colors = (46, 40, 46, 40, 46, 22) if ok else (196, 160, 196, 160, 196, 52)
        shadow = 22 if ok else 52
        for row in self.pixel_rows(word, colors, shadow):
            box_center(row)
        lead_color = self.ph if ok else self.red
        box_center(f"{lead_color}{headline}{self.reset}")
        if warnings:
            box_center(f"{self.escape('38;5;221')}{warnings}{self.reset}")
        box_line()
        self.write(f"   {self.medium}█{'▄' * inner}█{self.reset}\n")
        if log_path is not None:
            self.write(f"   {self.dark}{self.t('Full details:', 'Détails complets :')} {log_path}{self.reset}\n")
        self.write("\n")


@contextmanager
def terminal_session(terminal: Terminal):
    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    terminal.cursor(False)
    try:
        yield
    finally:
        termios.tcsetattr(fd, termios.TCSANOW, saved)
        terminal.cursor(True)


def read_key() -> str:
    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    try:
        # Keep ISIG enabled: Ctrl-C still reaches the normal cleanup path.
        tty.setcbreak(fd, termios.TCSANOW)
        key = os.read(fd, 1)
        if not key or key == b"\x04":
            raise EOFError
        if key == b"\x1b":
            for _ in range(2):
                if not select.select([fd], [], [], 0.05)[0]:
                    break
                key += os.read(fd, 1)
        if key in (b"\x1b[A", b"\x1bOA", b"k", b"K"):
            return "up"
        if key in (b"\x1b[B", b"\x1bOB", b"j", b"J"):
            return "down"
        if key in (b"\r", b"\n"):
            return "enter"
        if key == b" ":
            return "space"
        if key in (b"q", b"Q", b"\x1b"):
            return "quit"
        return key.decode("ascii", errors="ignore")
    finally:
        termios.tcsetattr(fd, termios.TCSANOW, saved)


PYTHON = "python"      # the main-menu entry that opens the Python modules menu


def is_python(project) -> bool:
    from .projects.python import PythonProject
    return isinstance(project, PythonProject)


def menu(terminal: Terminal, title: tuple[str, str], rows: list[tuple[str, str, bool]],
         selected: int, last: tuple[str, str], note: str = "") -> int | None:
    """Arrow/j-k/digit menu. rows = (label, description, custom); a last row
    (QUIT or BACK) follows. Returns the chosen row index, or None for the last
    row / q."""
    labels = rows + [(terminal.t(*last), "", False)]
    while True:
        terminal.heading(*title)
        for index, (label, description, custom) in enumerate(labels):
            shade = terminal.escape("38;5;80") if custom else terminal.medium
            if index == selected:
                terminal.write(f"   {terminal.inverse}▶ {label:<15}{terminal.reset} {terminal.ph}{description}{terminal.reset}\n")
            else:
                terminal.write(f"     {shade}{label:<15}{terminal.reset} {shade if custom else terminal.dark}{description}{terminal.reset}\n")
        shortcuts = " ".join(str(i) for i in range(1, min(len(rows), 9) + 1))
        terminal.write(f"\n   {terminal.dark}" + terminal.t(
            f"↑ ↓ select · Enter confirm · {shortcuts} shortcuts · q {last[0].lower()}",
            f"↑ ↓ choisir · Entrée valider · {shortcuts} raccourcis · q {last[1].lower()}") + terminal.reset + "\n")
        if note:
            terminal.write(f"   {terminal.dark}{note}{terminal.reset}\n")
        key = read_key()
        if key == "up":
            selected = (selected - 1) % len(labels)
        elif key == "down":
            selected = (selected + 1) % len(labels)
        elif key.isdigit() and 1 <= int(key) <= len(rows):
            return int(key) - 1
        elif key == "quit" or (key == "enter" and selected == len(rows)):
            return None
        elif key == "enter":
            return selected


def choose_project(terminal: Terminal, registry: Registry):
    projects = registry.projects
    guess = registry.detect(Path.cwd())
    descriptions = {
        "libft": terminal.t("libft.a · 43 functions · parts 1, 2, 3", "libft.a · 43 fonctions · parties 1, 2, 3"),
        "printf": terminal.t("libftprintf.a · cspdiuxX% · bonus -0. width # +", "libftprintf.a · cspdiuxX% · bonus -0. largeur # +"),
        "gnl": "get_next_line · 14 BUFFER_SIZE · bonus multi-fd",
        "push_swap": terminal.t("4 strategies · --bench · 100/500 numbers · bonus checker",
                                "4 stratégies · --bench · 100/500 nombres · bonus checker"),
        "py00": terminal.t("Growing Code · ex0-ex7 · flake8 · mypy", "Growing Code · ex0-ex7 · flake8 · mypy"),
        "py01": terminal.t("Code Cultivation · ex0-ex6 · OOP · flake8 · mypy",
                           "Code Cultivation · ex0-ex6 · POO · flake8 · mypy"),
        "py02": terminal.t("Garden Guardian · ex0-ex4 · exceptions · flake8 · mypy",
                           "Garden Guardian · ex0-ex4 · exceptions · flake8 · mypy"),
    }
    python = [project for project in projects if is_python(project) and not project.custom]
    # main menu: the C projects, one entry for every Python module, then custom suites
    entries: list = [p for p in projects if not p.custom and not is_python(p)]
    if python:
        entries.append(PYTHON)
    entries += [p for p in projects if p.custom]

    def row(entry) -> tuple[str, str, bool]:
        if entry == PYTHON:
            names = ", ".join(p.key for p in python)
            return ("PYTHON MODULES", terminal.t(f"{len(python)} modules · {names} ›", f"{len(python)} modules · {names} ›"), False)
        label = entry.name if entry.custom else entry.key.upper() if entry.key != "printf" else "FT_PRINTF"
        return (label, ("[CUSTOM] " if entry.custom else "") + descriptions.get(entry.key, entry.name), entry.custom)

    note = terminal.t(f"(current directory: {guess.key} detected)",
                      f"(dossier courant : {guess.key} détecté)") if guess else ""
    selected = entries.index(PYTHON if guess in python else guess) if guess in python or guess in entries else 0
    while True:
        choice = menu(terminal, ("WHICH PROJECT TO TEST?", "QUEL PROJET ON TORTURE ?"),
                      [row(entry) for entry in entries], selected, ("QUIT", "QUITTER"), note)
        if choice is None:
            terminal.clear()
            raise EOFError
        if entries[choice] != PYTHON:
            return entries[choice]
        selected = choice
        module = menu(terminal, ("WHICH PYTHON MODULE?", "QUEL MODULE PYTHON ?"),
                      [(p.key.upper(), f"{p.name} · " + descriptions.get(p.key, ""), False) for p in python],
                      python.index(guess) if guess in python else 0, ("BACK", "RETOUR"), note)
        if module is not None:
            return python[module]


def complete_path(value: str, state: int):
    matches = sorted(glob.glob(glob.escape(os.path.expanduser(value)) + "*"))
    matches = [path + (os.sep if os.path.isdir(path) else "") for path in matches]
    # Preserve the user's ~ spelling in the editable input.
    if value.startswith("~/"):
        matches = ["~" + path[len(str(Path.home())):] for path in matches]
    return matches[state] if state < len(matches) else None


def path_input(terminal: Terminal, default: str) -> str:
    completer, delimiters = readline.get_completer(), readline.get_completer_delims()
    readline.set_completer(complete_path)
    readline.set_completer_delims("\n")
    readline.parse_and_bind("tab: complete")
    readline.set_startup_hook(lambda: readline.insert_text(default))
    terminal.cursor(True)
    try:
        # Readline needs nonprinting markers to calculate the cursor position.
        prompt = f"   \001{terminal.ph}\002▶\001{terminal.reset}\002 " + terminal.t("path : ", "chemin : ")
        return input(prompt)
    finally:
        readline.set_startup_hook(None)
        readline.set_completer(completer)
        readline.set_completer_delims(delimiters)
        terminal.cursor(False)


def choose_path(terminal: Terminal, project) -> Path:
    home_project = Path.home() / project.name
    default = Path.cwd() if project.matches(Path.cwd()) else home_project
    if not project.matches(default):
        default = Path.cwd()
    error = ""
    while True:
        terminal.heading(f"WHERE IS YOUR {project.name} ?", f"OÙ EST TON {project.name} ?", project)
        if error:
            terminal.write(f"   {terminal.red}✘ {error}{terminal.reset}\n\n")
        terminal.write(f"   {terminal.dark}" + terminal.t("Tab to complete · Enter to confirm", "Tab pour compléter · Entrée pour valider") + terminal.reset + "\n\n")
        value = path_input(terminal, str(default))
        directory = Path(value).expanduser()
        if not directory.is_dir():
            error = terminal.t("directory not found: ", "dossier introuvable : ") + value
        elif project.requires_makefile and not (directory / "Makefile").is_file():
            error = terminal.t("no Makefile in ", "pas de Makefile dans ") + value
        elif project.header and not project.find_header(directory):
            error = terminal.t(f"no {project.header} in ", f"pas de {project.header} dans ") + value
        elif not project.custom and not project.header and not project.matches(directory):
            error = terminal.t(f"no {project.name} files in ", f"aucun fichier {project.name} dans ") + value
        else:
            return directory.resolve()
        default = directory


def choose_options(terminal: Terminal, project, options: Options) -> Options:
    is_python = not project.custom and not project.requires_compiler
    labels = [
        terminal.t("strict mode (-s): ▲ count as errors", "mode strict (-s) : les ▲ comptent comme erreurs"),
        terminal.t("verbose (-v): all failure details", "verbose (-v) : tous les détails des échecs"),
        terminal.t(
            f"efficiency (-e): your operation count vs the subject's \"excellent\", target {options.efficiency_target}%",
            f"efficacité (-e) : tes opérations face au seuil « excellent » du sujet, objectif {options.efficiency_target} %",
        ) if project.key == "push_swap" else terminal.t(
            f"efficiency (-e): your time vs this machine's perfect time, target {options.efficiency_target}%",
            f"efficacité (-e) : ton temps face au temps parfait de la machine, objectif {options.efficiency_target} %",
        ),
        terminal.t("checks (files, flake8, mypy, AST…)", "vérifications (fichiers, flake8, mypy, AST…)") if is_python else terminal.t(
            "checks (Makefile, nm, prototypes, README…)", "vérifications (Makefile, nm, prototypes, README…)"),
        terminal.t("chill mode (-c): style/hygiene check KOs become ▲", "mode chill (-c) : les vérifs style/hygiène KO deviennent ▲"),
        "flake8 / mypy" if is_python else "norminette",
        terminal.t("ignore hidden files (--no-hidden)", "ignorer les fichiers cachés (--no-hidden)"),
    ]
    keys = ["speculative", "verbose", "efficiency", "checks", "chill", "norm", "ignore_hidden"]
    if project.custom:
        # Subject/norm/include switches have no meaning for user command suites.
        labels, keys = labels[:2], keys[:2]
    elif is_python:
        # C efficiency benchmarks do not apply to Python modules.
        labels = [labels[0], labels[1], *labels[3:]]
        keys = [keys[0], keys[1], *keys[3:]]
    values = [getattr(options, key) for key in keys]
    selected = len(labels)
    while True:
        terminal.clear()
        terminal.banner(project)
        terminal.write(f"   {terminal.bold}{terminal.ph}OPTIONS{terminal.reset}  {terminal.dark}{project.name} · {options.directory}{terminal.reset}\n\n")
        for index, label in enumerate(labels):
            box = "[■]" if values[index] else "[ ]"
            if index == selected:
                terminal.write(f"   {terminal.ph}{terminal.bold}▶ {box} {label}{terminal.reset}\n")
            else:
                terminal.write(f"     {terminal.medium}{box}{terminal.reset} {terminal.dark}{label}{terminal.reset}\n")
        launch = terminal.t("START TESTING", "LANCER LA TORTURE")
        terminal.write(f"\n   {terminal.inverse} ▶ {launch} {terminal.reset}\n" if selected == len(labels)
                       else f"\n     {terminal.medium}▶ {launch}{terminal.reset}\n")
        terminal.write(f"\n   {terminal.dark}" + terminal.t(
            "↑ ↓ navigate · Space toggle · Enter start · q quit",
            "↑ ↓ naviguer · Espace cocher · Entrée lancer · q quitter") + terminal.reset + "\n")
        key = read_key()
        if key == "up":
            selected = (selected - 1) % (len(labels) + 1)
        elif key == "down":
            selected = (selected + 1) % (len(labels) + 1)
        elif key in ("space", "enter") and selected < len(labels):
            values[selected] = not values[selected]
        elif key == "enter":
            return replace(options, **dict(zip(keys, values)))
        elif key == "quit":
            terminal.clear()
            raise EOFError


def interactive(options: Options, registry: Registry | None = None):
    terminal = Terminal(options.lang, options.no_color)
    with terminal_session(terminal):
        project = choose_project(terminal, registry or Registry())
        options = replace(options, directory=choose_path(terminal, project))
        options = choose_options(terminal, project, options)
    terminal.clear()
    return project, options


def run_header(project, options: Options) -> None:
    terminal = Terminal(options.lang, options.no_color)
    terminal.banner(project)
    mode = terminal.t("strict (-s): ▲ count as errors", "strict (-s) : les ▲ comptent comme erreurs") if options.speculative else terminal.t(
        "normal: ▲ are warnings (-s to count them)", "normal : ▲ = avertissements (-s pour les compter)")
    if options.chill:
        mode += terminal.t(" · chill (-c): hygiene KOs -> ▲", " · chill (-c) : hygiène KO -> ▲")
    for label, value in ((terminal.t("project", "projet"), project.name),
                         (terminal.t("path", "chemin"), options.directory), ("mode  ", mode), ("seed  ", options.seed)):
        terminal.write(f"   {terminal.dark}{label}{terminal.reset} {value}\n")


def run_footer(options: Options) -> None:
    terminal = Terminal(options.lang, options.no_color)
    amber = terminal.escape("38;5;221")
    title = terminal.t("DISCLAIMER", "AVERTISSEMENT")
    lines = terminal.t(
        "ftorture is built to be ruthless and torture your code,\n"
        "but it can still miss bugs or edge cases. It is only a tool and\n"
        "never replaces your own review, testing, or human evaluation.",
        "ftorture est conçu pour être impitoyable et torturer ton code,\n"
        "mais il peut manquer des bugs ou des cas limites. Ce n'est qu'un\n"
        "outil : il ne remplace jamais ta propre vérification humaine.",
    ).splitlines()
    terminal.write(f"   {amber}▲ {title}{terminal.reset} {terminal.dark}· {lines[0]}{terminal.reset}\n")
    for line in lines[1:]:
        terminal.write(f"     {terminal.dark}{line}{terminal.reset}\n")
    terminal.write("\n")
