"""Rendering parity and real pseudo-terminal keyboard interaction."""
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import pty
import select
import signal
import subprocess
import sys
import tempfile
import termios
import time
import unittest
from unittest.mock import patch

from ftorture.runtime import Options
from ftorture.ui import Terminal, complete_path

ROOT = Path(__file__).resolve().parent.parent
CHILD = '''
import json
from dataclasses import asdict
from unittest.mock import patch
from ftorture.cli import main
def capture(ctx, project):
    print("SELECTED:" + json.dumps({"project": project.key, **asdict(ctx.options)}, default=str), flush=True)
    return 0
with patch("ftorture.cli.execute", capture):
    raise SystemExit(main())
'''


class PtySession:
    def __init__(self, directory, args=()):
        self.master, self.slave = pty.openpty()
        self.saved = termios.tcgetattr(self.slave)
        env = {**os.environ, "PYTHONPATH": str(ROOT), "LANG": "fr_FR.UTF-8"}
        self.process = subprocess.Popen([sys.executable, "-c", CHILD, *args], cwd=directory,
                                        env=env, stdin=self.slave, stdout=self.slave, stderr=self.slave)
        self.output = b""

    def send(self, data):
        os.write(self.master, data)

    def expect(self, text):
        expected = text.encode()
        deadline = time.monotonic() + 8
        while expected not in self.output:
            if time.monotonic() > deadline:
                raise AssertionError(f"Missing {text!r}: {self.output.decode(errors='replace')}")
            if select.select([self.master], [], [], 0.1)[0]:
                self.output += os.read(self.master, 65536)
            elif self.process.poll() is not None:
                raise AssertionError(f"Exited before {text!r}: {self.output!r}")
        position = self.output.index(expected) + len(expected)
        found, self.output = self.output[:position], self.output[position:]
        return found.decode(errors="replace")

    def finish(self, status=0):
        self.process.wait(timeout=8)
        if self.process.returncode != status:
            raise AssertionError(f"Unexpected status {self.process.returncode}")
        if termios.tcgetattr(self.slave) != self.saved:
            raise AssertionError("Terminal attributes were not restored")

    def close(self):
        if self.process.poll() is None:
            self.process.kill()
        self.process.wait()
        os.close(self.master)
        os.close(self.slave)


class TuiTests(unittest.TestCase):
    def test_custom_suite_is_distinct_and_selectable_in_main_menu(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifests = Path(tmp) / "tests"
            manifests.mkdir()
            (manifests / "mine.json").write_text(json.dumps({
                "version": 1, "key": "mine", "name": "My personal suite",
                "tests": [{"name": "one", "command": ["true"]}]}))
            session = self.session(tmp, ("--lang", "en", "--no-color", "--custom-tests-dir", str(manifests)))
            session.expect("[CUSTOM]")
            session.expect("q quit")
            session.send(b"4")
            session.expect("path : ")
            session.send(b"\n")
            session.expect("Enter start · q quit")
            session.send(b"\n")
            session.expect("SELECTED:")
            selected = json.loads(session.expect("\n").strip())
            self.assertEqual(selected["project"], "custom-mine")
            session.finish()

    def session(self, directory, args=()):
        session = PtySession(directory, args)
        self.addCleanup(session.close)
        return session

    def test_original_french_banner_snapshot(self):
        # Freeze the original 3x5 glyphs and one-pixel drop shadow, not just a title.
        output = io.StringIO()
        with redirect_stdout(output):
            Terminal("fr", no_color=True).banner()
        rows = output.getvalue().splitlines()
        self.assertEqual(rows[1], "   ██████  ██████  ██████  ████    ██████  ██  ██  ████    ██████  ")
        self.assertEqual(rows[6], "     ▒▒        ▒▒    ▒▒▒▒▒▒  ▒▒  ▒▒    ▒▒    ▒▒▒▒▒▒  ▒▒  ▒▒  ▒▒▒▒▒▒")
        self.assertEqual(rows[7:9], ["   ▚▚ 42 TESTER · LIBFT · FT_PRINTF · GET_NEXT_LINE ▞▞", "   > ton code va parler_"])
        self.assertNotIn("\033", output.getvalue())

    def test_color_palette_and_no_color_environment(self):
        with patch("sys.stdout.isatty", return_value=True), patch.dict(os.environ, {}, clear=True):
            terminal = Terminal("fr")
            self.assertIn("38;5;46", terminal.ph)
            self.assertIn("48;5;46", terminal.inverse)
            with patch.dict(os.environ, {"NO_COLOR": "1"}):
                self.assertFalse(Terminal("fr").color)

    def test_completion_handles_spaces_and_literal_glob_characters(self):
        with tempfile.TemporaryDirectory(prefix="ftorture [path] ") as tmp:
            directory = Path(tmp) / "student project"
            directory.mkdir()
            self.assertEqual(complete_path(str(Path(tmp) / "student"), 0), str(directory) + "/")
            self.assertIsNone(complete_path(str(Path(tmp) / "student"), 1))

    def test_all_screens_autodetection_options_and_cli_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "get_next_line.h").touch()
            session = self.session(tmp, ("--lang", "fr", "--no-color", "--seed", "17", "-f", "42"))
            session.expect("(dossier courant : gnl détecté)")
            session.send(b"\n")
            session.expect("chemin : ")
            session.send(b"\n")
            session.expect("Entrée lancer · q quitter")
            # Launch is selected initially. Wrap through every checkbox and toggle it.
            session.send(b"j j j j j j\n")
            result = session.expect("SELECTED:")
            payload = session.expect("\n").strip()
            options = json.loads(payload)
            self.assertEqual(options["project"], "gnl")
            self.assertEqual(options["directory"], tmp)
            self.assertEqual(options["seed"], 17)
            self.assertEqual(options["functions"], "42")
            for key in ("speculative", "verbose", "ignore_hidden"):
                self.assertTrue(options[key])
            self.assertFalse(options["checks"])
            self.assertFalse(options["norm"])
            self.assertNotIn("\033[38;", result)
            session.finish()

    def test_shortcut_path_validation_and_tab_completion(self):
        with tempfile.TemporaryDirectory(prefix="ftorture tui ") as tmp:
            project = Path(tmp) / "student project"
            project.mkdir()
            (project / "get_next_line.h").touch()
            session = self.session(tmp, ("--lang", "en", "--no-color"))
            session.expect("q quit")
            session.send(b"3")
            session.expect("path : ")
            session.send(b"\x15/no/such/ftorture-directory\n")
            session.expect("directory not found:")
            session.expect("path : ")
            session.send(b"\x15" + str(Path(tmp) / "student").encode() + b"\t\n")
            session.expect("Enter start · q quit")
            session.send(b"\n")
            session.expect("SELECTED:")
            options = json.loads(session.expect("\n").strip())
            self.assertEqual(options["directory"], str(project))
            session.finish()

    def test_arrow_keys_and_quit_restore_terminal(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = self.session(tmp)
            session.expect("q quitter")
            session.send(b"\x1b[A\n")  # wrap from LIBFT to QUITTER
            session.finish()
            session.expect("\033[?25h")

    def test_signal_during_menu_restores_terminal(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = self.session(tmp)
            session.expect("q quitter")
            session.process.send_signal(signal.SIGTERM)
            session.finish(130)
            session.expect("\033[?25h")

    def test_eof_during_path_restores_terminal(self):
        with tempfile.TemporaryDirectory() as tmp:
            session = self.session(tmp)
            session.expect("q quitter")
            session.send(b"3")
            session.expect("chemin : ")
            session.send(b"\x15\x04")
            session.finish()
