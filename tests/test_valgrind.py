"""valgrind pass: memcheck log parsing and an end-to-end run on a libft."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from ftorture.valgrind import collect

ROOT = Path(__file__).resolve().parent.parent

UNINIT = """==10== Conditional jump or move depends on uninitialised value(s)
==10==    at 0x420F4D: zt_fn_13 (/ftorture/src/libft/t_part2.c:141)
==10==    by 0x40706D: run_child (/ftorture/src/engine.c:447)
==10==  Uninitialised value was created by a heap allocation
==10==    at 0x4848899: malloc (in /usr/libexec/valgrind/vgpreload_memcheck-amd64-linux.so)
==10==    by 0x42D0F0: ft_calloc ({root}/ft_calloc.c:25)
==10==    by 0x420F00: zt_fn_13 (/ftorture/src/libft/t_part2.c:139)
"""
INVALID = """==11== Invalid write of size 1
==11==    at 0x42CC0A: ft_memset ({root}/srcs/ft_memset.c:24)
==11==    by 0x42D0F9: ft_calloc ({root}/ft_calloc.c:27)
==11==  Address 0x4a8f04a is 0 bytes after a block of size 10 alloc'd
"""
NULL_READ = """==12== Invalid read of size 1
==12==    at 0x42CBA8: ft_strlen ({root}/ft_strlen.c:20)
==12==  Address 0x0 is not stack'd, malloc'd or (recently) free'd
"""


class CollectTests(unittest.TestCase):
    def test_memcheck_errors_are_tied_to_the_student_code_and_tests(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, logs = Path(tmp) / "student", Path(tmp) / "logs"
            (root / "srcs").mkdir(parents=True)
            logs.mkdir()
            (logs / "tests.tsv").write_text("1\tft_calloc\t0\t1\tzeroed\n2\tft_calloc\t0\t2\tbig\n"
                                            "3\tft_strlen\t0\t1\tNULL\n4\tft_memset\t0\t1\tcrash like libc\n")
            for pid, seq, ref, body in ((10, 1, 0, UNINIT), (11, 2, 0, INVALID), (12, 3, 0, NULL_READ),
                                        (13, 4, 0, INVALID), (14, 1, 1, INVALID), (15, 9, 0, INVALID)):
                (logs / f"vg.{pid}").write_text(body.format(root=root).replace("==1", f"=={pid}"[:3]))
                if pid != 15:
                    (logs / f"pid{pid}").write_text(f"{seq} {ref}\n")
            (logs / "vg.99").write_text(INVALID.format(root=root))  # the parent: no pid file
            findings = collect(logs, root, {("ft_memset", 1): 1})
            where = {f.where: f for f in findings}
            self.assertEqual(set(where), {"ft_calloc.c:25", "srcs/ft_memset.c:24"})
            self.assertIn("uninitialised", where["ft_calloc.c:25"].message)
            self.assertIn("malloc of ft_calloc, ft_calloc.c:25", where["ft_calloc.c:25"].message)
            self.assertEqual(where["srcs/ft_memset.c:24"].tests, ["ft_calloc · big"])  # not the libc-crash test


@unittest.skipUnless(shutil.which("valgrind") and shutil.which("cc") and shutil.which("make"),
                     "needs valgrind and C build tools")
class ValgrindRunTests(unittest.TestCase):
    def test_uninitialised_read_only_valgrind_sees(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "libft.h").write_text("#include <stddef.h>\nsize_t ft_strlen(const char *s);\n")
            # the result is right, but a branch depends on a byte malloc left uninitialised
            (directory / "ft_strlen.c").write_text(
                '#include <stdlib.h>\n#include "libft.h"\nsize_t ft_strlen(const char *s)\n{\n'
                '\tsize_t\tn = 0;\n\tchar\t*junk = malloc(1);\n\n\tif (junk && *junk == 42)\n\t\tn = 0;\n'
                '\tfree(junk);\n\twhile (s[n])\n\t\tn++;\n\treturn (n);\n}\n')
            (directory / "Makefile").write_text(
                "NAME = libft.a\nall: $(NAME)\n$(NAME): ft_strlen.o\n\tar rcs $@ $<\n"
                "ft_strlen.o: ft_strlen.c\n\tcc -Wall -Wextra -Werror -c $< -o $@\n"
                "clean:\n\trm -f ft_strlen.o\nfclean: clean\n\trm -f $(NAME)\nre: fclean all\n")
            run = [sys.executable, str(ROOT / "torture.py"), "libft", str(directory), "--no-checks",
                   "--no-sanitize", "-f", "strlen", "--lang", "en", "--no-color"]
            result = subprocess.run(run, capture_output=True, text=True, timeout=600)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("VALGRIND", result.stdout)
            self.assertIn("ft_strlen.c:8", result.stdout)   # the branch
            self.assertIn("malloc of ft_strlen, ft_strlen.c:6", result.stdout)
            self.assertIn("Conditional jump or move depends on uninitialised value", result.stdout)
            result = subprocess.run([*run, "--no-valgrind"], capture_output=True, text=True, timeout=600)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn("VALGRIND", result.stdout)


if __name__ == "__main__":
    unittest.main()
