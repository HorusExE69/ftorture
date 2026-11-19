"""Regression tests for native file/include/prototype/symbol policies."""
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from ftorture.checks import CheckSession
from ftorture.runtime import Context, Options
from ftorture.subject.common import allowed_path, check_files, check_norm, check_readme, check_symbols
from ftorture.subject.includes import IncludeAnalysis, declarations, include_list, strip_c
from ftorture.subject.prototypes import check_prototypes
from ftorture.subject.archive import archive_checks
from ftorture.projects.libft import PROJECT as LIBFT

ROOT = Path(__file__).resolve().parent.parent


@contextmanager
def session_for(key="gnl"):
    with tempfile.TemporaryDirectory(prefix="native checks '") as tmp:
        root = Path(tmp)
        student = root / "student"
        student.mkdir()
        ctx = Context(root, key, Options(student, norm=False))
        ctx.build.mkdir(parents=True)
        # Expected signatures are part of the tester, never supplied by students.
        (root / "protos").mkdir()
        shutil.copy(ROOT / "protos" / f"{key}.txt", root / "protos" / f"{key}.txt")
        yield CheckSession(ctx), student


class FilePolicyTests(unittest.TestCase):
    def test_no_hidden_prunes_files_directories_and_include_analysis(self):
        with session_for() as (session, student):
            (student / ".vscode").mkdir()
            (student / ".vscode/hidden.c").write_text("#include <stdio.h>\n")
            (student / ".DS_Store").touch()
            session.ctx.options = replace(session.ctx.options, ignore_hidden=True)
            check_files(session, lambda path: allowed_path("gnl", path))
            self.assertTrue(session.report.records[-1].startswith("C|OK|Extra files|"))
            self.assertFalse(IncludeAnalysis(session).sources)
            (student / "extra.py").touch()
            check_files(session, lambda path: allowed_path("gnl", path))
            self.assertTrue(any("extra.py" in record for record in session.report.records))

    def test_submission_policies(self):
        self.assertTrue(allowed_path("libft", "ft_strlen.c"))
        self.assertFalse(allowed_path("libft", "extra.txt"))
        self.assertFalse(allowed_path("libft", "src/ft_strlen.c"))
        self.assertTrue(allowed_path("printf", "libft/libft.h"))
        self.assertFalse(allowed_path("printf", "libft/deeper/file.c"))
        self.assertTrue(allowed_path("gnl", "get_next_line_utils_bonus.c"))
        self.assertFalse(allowed_path("gnl", "get_next_line_utils.h"))

    def test_git_is_ignored_and_extra_files_fail(self):
        with session_for() as (session, student):
            (student / ".git").mkdir()
            (student / ".git/config").write_text("private metadata")
            (student / "get_next_line.c").write_text("")
            check_files(session, lambda path: allowed_path("gnl", path))
            self.assertTrue(any(record.startswith("C|OK|Extra files|") for record in session.report.records))
            (student / ".cache").mkdir()
            (student / "extra.py").write_text("")
            session.report.records.clear()
            check_files(session, lambda path: allowed_path("gnl", path))
            self.assertTrue(any(record.startswith("C|KO|Extra files|") for record in session.report.records))
            self.assertTrue(any(".cache" in record for record in session.report.records))

    def test_readme_and_algorithm(self):
        with session_for() as (session, student):
            check_readme(session, algorithm=True)
            self.assertTrue(session.report.records[-1].startswith("C|KO|README.md|"))
            (student / "README.md").write_text(
                "*This project has been created as part of the 42 curriculum by student*\n"
                "# Description\n# Instructions\n# Resources\nAlgorithm: read one line.\n")
            check_readme(session, algorithm=True)
            self.assertTrue(session.report.records[-1].startswith("C|OK|README.md|"))

    def test_norminette_failure_and_disabled(self):
        with session_for() as (session, _):
            check_norm(session)
            self.assertTrue(session.report.records[-1].startswith("C|SKIP|Norminette|"))
            session.ctx = Context(session.ctx.root, "gnl", Options(session.ctx.options.directory))
            with patch("ftorture.subject.common.shutil.which", return_value="/norminette"), \
                    patch.object(session, "capture", return_value=(1, "file.c: Error!\nError: BAD_STYLE\n")):
                check_norm(session)
            self.assertTrue(any(record.startswith("C|KO|Norminette|") for record in session.report.records))

    def test_forbidden_symbols_globals_helpers_and_missing_functions(self):
        with session_for("libft") as (session, _):
            entries = [("T", "ft_strlen", "libft.a:ft_strlen.o"), ("T", "helper", "libft.a:helper.o"),
                       ("U", "printf", "libft.a:ft_strlen.o"), ("D", "global", "libft.a:ft_strlen.o")]
            check_symbols(session, entries, allowed={"malloc", "free", "write"},
                          required=["ft_strlen", "ft_split"], libft=True)
            records = session.report.records
            for label in ("External functions", "Global variables", "Mandatory functions"):
                self.assertTrue(any(record.startswith(f"C|KO|{label}|") for record in records), records)
            self.assertTrue(any(record.startswith("C|WARN|Helper functions|") for record in records))
            self.assertTrue(any("printf" in record for record in records))


class LexerTests(unittest.TestCase):
    def test_comments_and_strings_do_not_justify_includes(self):
        source = '/* malloc */\n// printf\nchar *s = "free // text";\nint n;'
        self.assertNotIn("malloc", strip_c(source))
        self.assertNotIn("printf", strip_c(source))
        self.assertNotIn("free", strip_c(source))
        self.assertIn('"free // text"', strip_c(source, strings=True))
        self.assertEqual(include_list('/* #include <bad.h> */\n#include "own.h"\n#include <stdlib.h>'),
                         [("usr", "own.h"), ("sys", "stdlib.h")])

    def test_function_typedef_struct_enum_and_macro_declarations(self):
        source = ("#define LIMIT 42\n"
                  "typedef struct s_node { int value; struct s_node *next; } t_node;\n"
                  "enum e_state { READY, DONE };\n"
                  "int work(const char *s);\n"
                  "typedef int (*callback)(int);\n")
        names = declarations(source)
        self.assertTrue({"LIMIT", "s_node", "t_node", "e_state", "READY", "DONE", "work", "callback"} <= names, names)
        self.assertNotIn("value", names)


@unittest.skipUnless(shutil.which("cc"), "compiler required")
class CompilerChecksTests(unittest.TestCase):
    def test_used_unused_and_duplicate_system_headers(self):
        with session_for() as (session, student):
            (student / "main.c").write_text(
                "#include <stdlib.h>\n#include <stdio.h>\n#include <stdlib.h>\n"
                'void *work(void) { return malloc(1); }\n')
            analysis = IncludeAnalysis(session)
            analysis.run()
            details = "\n".join(session.report.records)
            self.assertIn("C|KO|Includes|2/3", details)
            self.assertIn("<stdio.h> unused", details)
            self.assertIn("<stdlib.h> included twice", details)

    def test_transitive_header_users_and_cycles(self):
        with session_for() as (session, student):
            (student / "a.h").write_text('#ifndef A_H\n#define A_H\n#include "b.h"\n#include <stdlib.h>\n#endif\n')
            (student / "b.h").write_text('#ifndef B_H\n#define B_H\n#include "a.h"\n#endif\n')
            (student / "main.c").write_text('#include "a.h"\nvoid *work(void) { return malloc(1); }\n')
            analysis = IncludeAnalysis(session)
            self.assertIn("malloc", analysis.provides(student / "a.h"))
            self.assertIn("malloc", analysis.provides(student / "b.h"))
            self.assertIn("malloc", analysis.users(student / "b.h"))
            analysis.run()
            self.assertTrue(any(record.startswith("C|OK|Includes|") for record in session.report.records),
                            session.report.records)

    def test_unknown_headers_get_no_verdict(self):
        with session_for() as (session, student):
            (student / "main.c").write_text("#include <not_a_real_library.h>\nint x;\n")
            IncludeAnalysis(session).run()
            self.assertTrue(any(record.startswith("C|OK|Includes|") for record in session.report.records))

    def test_common_type_does_not_justify_duplicate_library(self):
        with session_for() as (session, student):
            (student / "main.c").write_text("#include <stddef.h>\n#include <stdio.h>\nsize_t size;\n")
            IncludeAnalysis(session).run()
            self.assertTrue(any("<stdio.h> only repeats" in record for record in session.report.records),
                            session.report.records)

    def test_correct_wrong_missing_and_non_self_contained_prototypes(self):
        for declaration, status in (("char *get_next_line(int fd);", "OK"),
                                    ("int get_next_line(int fd);", "KO"), ("int another(int fd);", "KO")):
            with self.subTest(declaration=declaration), session_for() as (session, student):
                (student / "get_next_line.h").write_text(declaration)
                check_prototypes(session, "get_next_line.h", "14.3")
                self.assertTrue(any(record.startswith(f"P|get_next_line|{status}|")
                                    for record in session.report.records), session.report.records)
        with session_for() as (session, student):
            (student / "get_next_line.h").write_text("size_t helper(void);\nchar *get_next_line(int fd);\n")
            check_prototypes(session, "get_next_line.h", "14.3")
            self.assertTrue(any(record.startswith("C|WARN|get_next_line.h self-contained|")
                                for record in session.report.records), session.report.records)

    def test_list_layout_rejects_wrong_field_types(self):
        for field in ("void *content", "int content"):
            with self.subTest(field=field), session_for("libft") as (session, student):
                (student / "libft.h").write_text(
                    f"typedef struct s_list {{ {field}; struct s_list *next; }} t_list;\n")
                check_prototypes(session, "libft.h", "19.3", linked_list=True)
                status = "OK" if field.startswith("void") else "KO"
                self.assertTrue(any(record.startswith(f"C|{status}|t_list structure|")
                                    for record in session.report.records), session.report.records)


@unittest.skipUnless(all(shutil.which(tool) for tool in ("cc", "make", "ar", "nm")),
                     "C build tools required")
class MakefileChecksTests(unittest.TestCase):
    def test_flags_relink_and_cleanup(self):
        for broken in (False, True):
            with self.subTest(broken=broken), session_for("libft") as (session, student):
                (student / "libft.h").write_text("#include <stddef.h>\nsize_t ft_strlen(const char *s);\n")
                (student / "ft_strlen.c").write_text(
                    '#include "libft.h"\nsize_t ft_strlen(const char *s) { size_t n = 0; while (s[n]) n++; return n; }\n')
                flags = "" if broken else "-Wall -Wextra -Werror"
                clean = "true" if broken else "rm -f ft_strlen.o"
                (student / "Makefile").write_text(
                    "NAME = libft.a\nall: $(NAME)\n$(NAME): ft_strlen.o\n\tar rcs $@ $<\n"
                    f"ft_strlen.o: ft_strlen.c\n\tcc {flags} -c $< -o $@\n"
                    f"clean:\n\t{clean}\nfclean: clean\n\trm -f $(NAME)\nre: fclean all\n"
                    + (".PHONY: $(NAME)\n" if broken else ""))
                try:
                    archive_checks(session.ctx, LIBFT, linked_list=True)
                    records = session.ctx.checks_file.read_text().splitlines()
                    status = "KO" if broken else "OK"
                    for label in ("Compiler flags", "Relink", "make clean"):
                        self.assertTrue(any(record.startswith(f"C|{status}|{label}|") for record in records), records)
                    for label in ("Makefile rules", "Compiler", "Archive", "make fclean"):
                        self.assertTrue(any(record.startswith(f"C|OK|{label}|") for record in records), records)
                finally:
                    LIBFT.cleanup(session.ctx)


if __name__ == "__main__":
    unittest.main()
