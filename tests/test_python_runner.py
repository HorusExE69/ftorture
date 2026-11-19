"""Run with python3 -m unittest discover -s tests -v (standard library only)."""
import importlib.util
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from ftorture.cli import execute, run_lock
from ftorture.checks import CheckReport
from ftorture.language import default_language
from ftorture.projects import detect, find
from ftorture.projects.gnl import PROJECT as GNL
from ftorture.runtime import Context, Options, RunnerError

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("ftorture_installer", ROOT / "install.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


class InstallerTests(unittest.TestCase):
    def test_python_only_installed_command_works_outside_checkout(self):
        self.assertFalse((ROOT / "torture.sh").exists())
        self.assertFalse((ROOT / "install.sh").exists())
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            target = installer.install(ROOT, home)
            elsewhere = home / "another directory"
            elsewhere.mkdir()
            result = subprocess.run([str(target), "--help"], cwd=elsewhere,
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("usage: torture", result.stdout)

    def test_uninstall_is_confirmed_idempotent_and_preserves_shell_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            target = installer.install(ROOT, home)
            (home / ".zshrc").write_text('export PATH="$HOME/.local/bin:$PATH"\n')
            env = {**os.environ, "HOME": tmp}
            for args in (("--delete",), ("--confirm",), ("--update", "--delete", "--confirm")):
                result = subprocess.run([sys.executable, str(ROOT / "install.py"), *args], env=env, capture_output=True)
                self.assertEqual(result.returncode, 2)
                self.assertTrue(target.exists())
            for _ in range(2):
                result = subprocess.run([sys.executable, str(ROOT / "install.py"), "--delete", "--confirm"], env=env, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(target.exists())
            self.assertIn(".local/bin", (home / ".zshrc").read_text())
            self.assertTrue(target.parent.is_dir())

    def test_uninstall_legacy_and_refuse_unrelated(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            target = home / ".local/bin/torture"
            target.parent.mkdir(parents=True)
            legacy = home / ".local/applications/torture.sh"
            legacy.parent.mkdir()
            legacy.write_text(f"#!/bin/sh\n{installer.MARKER}\n")
            target.symlink_to(legacy)
            installer.uninstall(home)
            self.assertFalse(legacy.exists())
            target.write_text("unrelated command")
            with self.assertRaises(RuntimeError):
                installer.uninstall(home)
            self.assertEqual(target.read_text(), "unrelated command")
            target.unlink()
            target.symlink_to(home / "unrelated-missing")
            with self.assertRaises(RuntimeError):
                installer.uninstall(home)
            self.assertTrue(target.is_symlink())

    def test_path_setup_preserves_content_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".bashrc").write_text("# my settings\n")
            (home / ".zshrc").write_text('export PATH="${HOME}/.local/bin:$PATH"\n')
            with patch.object(installer, "detect_shell", return_value="bash"), \
                    patch("sys.stdin.isatty", return_value=True), patch("builtins.input", return_value="yes") as ask:
                installer.configure_path(home)
                installer.configure_path(home)
            ask.assert_called_once()
            content = (home / ".bashrc").read_text()
            self.assertTrue(content.startswith("# my settings\n"))
            self.assertEqual(content.count(installer.PATH_MARKER), 1)
            self.assertNotIn(installer.PATH_MARKER, (home / ".zshrc").read_text())
            self.assertFalse((home / ".config/fish/config.fish").exists())

    def test_path_setup_only_edits_current_shell(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            with patch.dict(os.environ, {"ZDOTDIR": str(home)}), \
                    patch.object(installer, "detect_shell", return_value="zsh"), \
                    patch("sys.stdin.isatty", return_value=True), patch("builtins.input", return_value="y"):
                installer.configure_path(home)
                installer.configure_path(home)
            self.assertTrue((home / ".zshrc").exists())
            self.assertFalse((home / ".bashrc").exists())
            self.assertFalse((home / ".config/fish/config.fish").exists())

    def test_path_setup_decline_and_noninteractive_never_edit(self):
        for interactive in (False, True):
            with self.subTest(interactive=interactive), tempfile.TemporaryDirectory() as tmp:
                home = Path(tmp)
                with patch.object(installer, "detect_shell", return_value="bash"), \
                        patch("sys.stdin.isatty", return_value=interactive), patch("builtins.input", return_value="n") as ask:
                    installer.configure_path(home)
                self.assertFalse((home / ".bashrc").exists())
                self.assertEqual(ask.call_count, int(interactive))

    def test_existing_path_is_detected_without_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".bashrc").write_text('export PATH="${HOME}/.local/bin:$PATH"\n')
            with patch.object(installer, "detect_shell", return_value="bash"), patch("builtins.input") as ask:
                installer.configure_path(home)
            ask.assert_not_called()
            self.assertFalse(installer.path_configured('# export PATH="$HOME/.local/bin:$PATH"', home))
            self.assertFalse(installer.path_configured('echo "$HOME/.local/bin"', home))

    def test_shell_detection_prefers_running_shell_and_falls_back(self):
        with patch.object(installer.Path, "read_text", return_value="zsh\n"), patch.dict(os.environ, {"SHELL": "/bin/bash"}):
            self.assertEqual(installer.detect_shell(), "zsh")
        with patch.object(installer.Path, "read_text", side_effect=OSError), patch.dict(os.environ, {"SHELL": "/bin/fish"}):
            self.assertEqual(installer.detect_shell(), "fish")

    def test_alternate_shell_configuration_paths(self):
        home = Path("/example/home")
        with patch.dict(os.environ, {"ZDOTDIR": "/custom/zsh", "XDG_CONFIG_HOME": "/custom/config"}):
            self.assertEqual(installer.shell_configuration(home, "zsh")[0], Path("/custom/zsh/.zshrc"))
            self.assertEqual(installer.shell_configuration(home, "fish")[0], Path("/custom/config/fish/config.fish"))
        self.assertIsNone(installer.shell_configuration(home, "unknown"))

    def test_migrate_reinstall_and_launch(self):
        with tempfile.TemporaryDirectory(prefix="ftorture home '") as tmp:
            home = Path(tmp)
            old = home / ".local/applications/old-launcher"
            old.parent.mkdir(parents=True)
            old.write_text(f"#!/usr/bin/env python3\n{installer.MARKER}\n")
            target = home / ".local/bin/torture"
            target.parent.mkdir(parents=True)
            target.symlink_to(old)
            installer.install(ROOT, home)
            self.assertFalse(old.exists())
            self.assertFalse(target.is_symlink())
            installer.install(ROOT, home)
            result = subprocess.run([str(target), "--list-projects"], cwd=home,
                                    capture_output=True, text=True, check=True)
            self.assertIn("get_next_line", result.stdout)
            self.assertTrue(target.read_text().startswith("#!/usr/bin/env python3"))

    def test_preserve_unrelated_files_and_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            old = home / ".local/applications/old-launcher"
            old.parent.mkdir(parents=True)
            old.write_text("unrelated\n")
            target = installer.install(ROOT, home)
            self.assertEqual(old.read_text(), "unrelated\n")
            target.write_text("unrelated command\n")
            with self.assertRaises(RuntimeError):
                installer.install(ROOT, home)
            self.assertEqual(target.read_text(), "unrelated command\n")
            target.unlink()
            target.symlink_to(old)
            with self.assertRaises(RuntimeError):
                installer.install(ROOT, home)
            self.assertEqual(old.read_text(), "unrelated\n")

    def test_fresh_install_does_not_create_applications(self):
        with tempfile.TemporaryDirectory() as tmp:
            installer.install(ROOT, Path(tmp))
            self.assertFalse((Path(tmp) / ".local/applications").exists())

    def test_update_refuses_dirty_checkout_and_uses_original(self):
        with patch.object(installer.subprocess, "check_output", side_effect=[str(ROOT), "main", " M foo"]):
            with patch.object(installer.subprocess, "run") as run:
                with self.assertRaisesRegex(RuntimeError, "local changes"):
                    installer.update(ROOT)
                run.assert_not_called()
        with patch.object(installer.subprocess, "check_output", side_effect=[str(ROOT), "main", ""]):
            with patch.object(installer.subprocess, "run") as run:
                installer.update(ROOT)
                self.assertEqual(run.call_args_list[0].args[0], [
                    "git", "-C", str(ROOT), "fetch", "https://github.com/HorusExE69/ftorture.git", "main"])
                self.assertIn("--ff-only", run.call_args_list[1].args[0])


class RunnerTests(unittest.TestCase):
    def test_native_check_report(self):
        report = CheckReport()
        report.section("Files")
        report.check("KO", "README", "missing | reason\nsecond line")
        report.prototype("example", "OK", "int example(void)", "int example(void)")
        report.end_prototypes()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "checks.txt"
            report.write(path)
            self.assertEqual(path.read_text().splitlines(), [
                "S|Files", "C|KO|README|missing / reason second line",
                "P|example|OK|int example(void)|int example(void)", "PS"])
        with self.assertRaises(ValueError):
            report.check("PASS", "bad status")

    def test_cleanup_after_interruption(self):
        class InterruptedProject:
            requires_compiler = True
            custom = False
            name = "fake"
            key = "fake"
            subject = "1"
            tools = ()
            cleaned = False

            def validate(self, ctx):
                pass

            def run(self, ctx):
                raise KeyboardInterrupt

            def cleanup(self, ctx):
                self.cleaned = True

        with tempfile.TemporaryDirectory() as tmp:
            project = InterruptedProject()
            ctx = Context(Path(tmp), "fake", Options(Path(tmp), checks=False))
            with patch("ftorture.cli.shutil.which", return_value="/usr/bin/cc"):
                with self.assertRaises(KeyboardInterrupt):
                    execute(ctx, project)
            self.assertTrue(project.cleaned)

    def test_locale_precedence(self):
        with patch.dict(os.environ, {"LC_ALL": "", "LC_MESSAGES": "fr_FR.UTF-8", "LANG": "en_US"}, clear=True):
            self.assertEqual(default_language(), "fr")
        with patch.dict(os.environ, {"LC_ALL": "C", "LANG": "fr_FR"}, clear=True):
            self.assertEqual(default_language(), "en")

    def test_aliases_and_detection(self):
        self.assertEqual(find("ft_printf").key, "printf")
        self.assertEqual(find("get_next_line").key, "gnl")
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            self.assertIsNone(detect(directory))
            (directory / "libft.h").touch()
            self.assertEqual(detect(directory).key, "libft")

    def test_lock_prevents_concurrent_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            with run_lock(Path(tmp)):
                with self.assertRaises(RunnerError):
                    with run_lock(Path(tmp)):
                        self.fail("second lock succeeded")

    def test_invalid_numeric_options(self):
        for arguments in (["--timeout", "0"], ["--seed", "-1"], ["-p", "x"], ["--lang", "de"]):
            result = subprocess.run([sys.executable, str(ROOT / "torture.py"), *arguments],
                                    capture_output=True)
            self.assertEqual(result.returncode, 2)

    def test_gnl_pass_selection(self):
        ctx = Context(ROOT, "gnl", Options(Path("/unused"), part=2, functions="1,42"))
        self.assertEqual(GNL.passes(ctx, bonus=True), [(2, "1", "bbs1"), (2, "42", "bbs42")])
        self.assertEqual(GNL.passes(ctx, bonus=False), [])


@unittest.skipUnless(all(shutil.which(tool) for tool in ("cc", "make", "nm")),
                     "integration tests require Linux C build tools")
class IntegrationTests(unittest.TestCase):
    def invoke(self, *arguments, cwd=None, env=None):
        return subprocess.run([sys.executable, str(ROOT / "torture.py"), *map(str, arguments)],
                              cwd=cwd, env=env, capture_output=True, text=True, timeout=90)

    def libft_fixture(self, directory: Path, broken: bool = False):
        (directory / "libft.h").write_text("#include <stddef.h>\nsize_t ft_strlen(const char *s);\n")
        body = "(void)s; return 0;" if broken else "size_t n = 0; while (s[n]) n++; return n;"
        (directory / "ft_strlen.c").write_text(f'#include "libft.h"\nsize_t ft_strlen(const char *s) {{ {body} }}\n')
        (directory / "Makefile").write_text(
            "NAME = libft.a\nall: $(NAME)\n$(NAME): ft_strlen.o\n\tar rcs $@ $<\n"
            "ft_strlen.o: ft_strlen.c\n\tcc -Wall -Wextra -Werror -c $< -o $@\n"
            "clean:\n\trm -f ft_strlen.o\nfclean: clean\n\trm -f $(NAME)\nre: fclean all\n")

    def test_libft_good_broken_and_cleanup(self):
        for broken in (False, True):
            with self.subTest(broken=broken), tempfile.TemporaryDirectory(prefix="student space '") as tmp:
                directory = Path(tmp)
                self.libft_fixture(directory, broken)
                result = self.invoke("libft", directory, "--no-checks", "-f", "strlen", "--lang", "en", "--no-color")
                self.assertEqual(result.returncode, int(broken), result.stdout + result.stderr)
                self.assertIn("RESULT", result.stdout)
                self.assertFalse((directory / "ft_strlen.o").exists())
                self.assertTrue((directory / "libft.a").is_file())

    def test_subject_checks_preserve_failures(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            self.libft_fixture(directory)
            result = self.invoke("libft", directory, "--no-norm", "-f", "strlen", "--lang", "en", "--no-color")
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("README.md", result.stdout)
            self.assertIn("Legend", result.stdout)
            self.assertFalse((directory / "ft_strlen.o").exists())

    def test_build_failure_is_operational_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            self.libft_fixture(directory)
            (directory / "ft_strlen.c").write_text("this will not compile\n")
            result = self.invoke("libft", directory, "--no-checks")
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertIn("make.log", result.stderr)

    def test_signal_stops_build_before_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "libft.h").write_text("")
            (directory / "slow.py").write_text(
                "from pathlib import Path\nimport time\n"
                "Path('ready').touch()\ntime.sleep(30)\nPath('should-not-exist').touch()\n")
            (directory / "Makefile").write_text(
                f"all:\n\t{sys.executable} slow.py\nclean:\n\ttouch cleaned\nfclean:\n\ttrue\n")
            with subprocess.Popen([sys.executable, str(ROOT / "torture.py"), "libft", str(directory),
                                   "--no-checks"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  text=True) as process:
                deadline = time.monotonic() + 8
                while not (directory / "ready").exists() and time.monotonic() < deadline:
                    if process.poll() is not None:
                        break
                    time.sleep(0.02)
                try:
                    self.assertTrue((directory / "ready").exists())
                    process.send_signal(signal.SIGTERM)
                    stdout, stderr = process.communicate(timeout=10)
                    self.assertEqual(process.returncode, 130, stdout + stderr)
                    self.assertTrue((directory / "cleaned").is_file())
                    self.assertFalse((directory / "should-not-exist").exists())
                finally:
                    if process.poll() is None:
                        process.kill()

    def test_directory_detection_and_french_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            self.libft_fixture(directory)
            result = self.invoke(directory, "--no-checks", "-f", "strlen", "--lang", "fr", "--no-color")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("RÉSULTAT", result.stdout)

    def test_printf_two_pass_stats_and_bonus_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "ft_printf.h").write_text("int ft_printf(const char *, ...);\n")
            (directory / "ft_printf.c").write_text(
                "#include <stdarg.h>\n#include <stdio.h>\n"
                "int ft_printf(const char *s, ...) { va_list a; va_start(a,s); "
                "int n = vprintf(s,a); va_end(a); return n; }\n")
            (directory / "Makefile").write_text(
                "all: libftprintf.a\nbonus: all\nlibftprintf.a: ft_printf.c\n"
                "\tcc -c ft_printf.c -o ft_printf.o\n\tar rcs $@ ft_printf.o\n"
                "clean:\n\trm -f ft_printf.o\nfclean: clean\n\trm -f libftprintf.a\n")
            for args in (("-f", "pf_d,pf_minus"), ("-p", "2", "-f", "pf_minus")):
                result = self.invoke("printf", directory, "--no-checks", "--lang", "en", "--no-color", *args)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(result.stdout.count("RESULT"), 1)
                self.assertFalse((directory / "ft_printf.o").exists())

    def test_gnl_broken_and_unknown_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "get_next_line.h").write_text("char *get_next_line(int fd);\n")
            (directory / "get_next_line.c").write_text("char *get_next_line(int fd) { (void)fd; return 0; }\n")
            (directory / "get_next_line_utils.c").write_text("")
            result = self.invoke("gnl", directory, "--no-checks", "-p", "1", "-f", "1,42", "--lang", "en")
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertEqual(result.stdout.count("RESULT"), 1)
            self.assertIn("BUFFER_SIZE=42", result.stdout)
            self.assertEqual(sorted(p.name for p in directory.iterdir()), [
                "get_next_line.c", "get_next_line.h", "get_next_line_utils.c"])
            result = self.invoke("gnl", directory, "--no-checks", "-f", "nonsense")
            self.assertEqual(result.returncode, 2)

    def test_gnl_link_failure_keeps_later_passes_and_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "get_next_line.h").write_text("char *get_next_line(int fd);\n")
            (directory / "get_next_line.c").write_text(
                "char *get_next_line(int fd) { (void)fd; return 0; }\n"
                "#if BUFFER_SIZE == 1\nint main(void) { return 0; }\n#endif\n")
            (directory / "get_next_line_utils.c").touch()
            result = self.invoke("gnl", directory, "--no-checks", "-p", "1", "-f", "1,42", "--lang", "en")
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("cannot link tester", result.stdout)
            self.assertIn("BUFFER_SIZE=42", result.stdout)
            self.assertEqual(result.stdout.count("RESULT"), 1)

    def test_gnl_good_mandatory_bonus(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = '''#include <stdlib.h>
#include <unistd.h>
char *get_next_line(int fd) {
    size_t n = 0, cap = 16;
    char *buf = malloc(cap), c;
    if (!buf) return NULL;
    for (;;) {
        ssize_t k = read(fd, &c, 1);
        if (k < 0 || (k == 0 && n == 0)) { free(buf); return NULL; }
        if (k == 0) break;
        if (n + 1 >= cap) {
            char *b = malloc(cap * 2);
            if (!b) { free(buf); return NULL; }
            for (size_t i = 0; i < n; i++) b[i] = buf[i];
            free(buf); buf = b; cap *= 2;
        }
        buf[n++] = c;
        if (c == '\\n') break;
    }
    buf[n] = 0;
    return buf;
}
'''
            for suffix in ("", "_bonus"):
                (directory / f"get_next_line{suffix}.h").write_text("char *get_next_line(int fd);\n")
                (directory / f"get_next_line{suffix}.c").write_text(source)
                (directory / f"get_next_line_utils{suffix}.c").write_text("")
            (directory / "README.md").write_text(
                "*This project has been created as part of the 42 curriculum by student*\n"
                "# Description\n# Instructions\n# Resources\nAlgorithm: read one byte at a time.\n")
            args = ["gnl", str(directory), "--no-norm", "-f", "1,42", "--lang", "en", "--no-color"]
            result = self.invoke(*args)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("PART 2", result.stdout)
            total = next(line for line in (ROOT / "ftorture.log").read_text().splitlines()
                                if line.startswith("TOTAL:"))
            self.assertIn("0 failed, 0 speculative, 0 missing", total)
            self.assertEqual(result.stdout.count("RESULT"), 1)


if __name__ == "__main__":
    unittest.main()
