"""-fsanitize pass: report parsing and an end-to-end run on a broken get_next_line."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from ftorture.sanitize import collect

ROOT = Path(__file__).resolve().parent.parent

UBSAN = """{root}/ft_itoa.c:25:8: runtime error: negation of -2147483648 cannot be represented in type 'int'; cast to an unsigned type to negate this value to itself
    #0 0x5555 in ft_itoa {root}/ft_itoa.c:25
    #1 0x5556 in zt_fn_12 /ftorture/src/libft/t_part2.c:80
"""
ASAN = """=================================================================
==42==ERROR: AddressSanitizer: stack-buffer-overflow on address 0x7ffd at pc 0x55 bp 0x7f sp 0x7f
WRITE of size 1 at 0x7ffd thread T0
    #0 0x5555 in fill {root}/srcs/fill.c:14:9
    #1 0x5556 in get_next_line {root}/get_next_line.c:40
    #2 0x5557 in zt_fn_3 /ftorture/src/gnl/t_gnl.c:50
"""
TESTER_ONLY = "==7==AddressSanitizer: WARNING: unexpected format specifier in printf interceptor: %k\n"


class CollectTests(unittest.TestCase):
    def test_reports_become_grouped_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, reports = Path(tmp) / "student", Path(tmp) / "reports"
            (root / "srcs").mkdir(parents=True)
            reports.mkdir()
            (reports / "tests.tsv").write_text(
                "1\tft_itoa\t0\t1\tINT_MIN\n2\tft_itoa\t1\t2\tsurprise\n3\tbs42\t0\t1\tlong line\n"
                "4\tpf_edge\t1\t1\t%k\n")
            (reports / "t1.100").write_text(UBSAN.format(root=root))
            (reports / "t2.101").write_text(UBSAN.format(root=root))
            (reports / "t3.102").write_text(ASAN.format(root=root))
            (reports / "t4.103").write_text(TESTER_ONLY)
            findings = collect(reports, root)  # no verdicts known: nothing cancels out
            self.assertEqual(len(findings), 2)
            asan = next(f for f in findings if f.kind == "stack-buffer-overflow")
            self.assertEqual((asan.function, asan.where), ("fill", "srcs/fill.c:14"))
            self.assertIn("WRITE of 1 bytes", asan.message)
            self.assertFalse(asan.speculative)
            ub = next(f for f in findings if f.kind == "signed-integer-overflow")
            self.assertEqual(ub.where, "ft_itoa.c:25")
            self.assertEqual(ub.tests, ["ft_itoa · INT_MIN", "ft_itoa · surprise"])
            self.assertFalse(ub.speculative)  # one occurrence in a normal test
            self.assertFalse(ub.compensated)
            # the normal pass got the right result in the normal test: it cancels out
            # (the speculative test does not count for that verdict)
            ub = next(f for f in collect(reports, root, lambda suite, index: index == 1) if f.overflow)
            self.assertTrue(ub.compensated)
            # wrong result in the normal test: a real error
            ub = next(f for f in collect(reports, root, lambda suite, index: index != 1) if f.overflow)
            self.assertFalse(ub.compensated)
            # an out-of-bounds access never cancels out
            asan = next(f for f in collect(reports, root, lambda s, i: True) if not f.overflow)
            self.assertFalse(asan.compensated)

    def test_cancelled_overflow_is_an_ok_line(self):
        from ftorture.sanitize import Finding, write
        from ftorture.runtime import Context, Options
        with tempfile.TemporaryDirectory() as tmp:
            ctx = Context(Path(tmp), "libft", Options(Path(tmp), lang="en"))
            ok = Finding("signed-integer-overflow", "ft_atoi.c:33", "ft_atoi", "2147483640 + 8", ["ft_atoi · INT_MIN"],
                         speculative=False, compensated=True)
            bad = Finding("signed-integer-overflow", "ft_itoa.c:20", "ft_itoa", "negation of -2147483648",
                          ["ft_itoa · INT_MIN"], speculative=False)
            records = write(ctx, [ok, bad]).read_text()
            self.assertIn("C|OK|ft_atoi|ft_atoi.c:33 · signed overflow that cancels out", records)
            self.assertIn("C|KO|ft_itoa|ft_itoa.c:20 · negation of -2147483648", records)


@unittest.skipUnless(shutil.which("cc"), "needs a C compiler")
class SanitizerRunTests(unittest.TestCase):
    def test_broken_gnl_is_caught_and_no_sanitize_skips(self):
        from ftorture.sanitize import available
        from ftorture.runtime import Context, Options
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            if not available(Context(directory, "probe", Options(directory))):
                self.skipTest("no ASan/UBSan runtime")
            (directory / "get_next_line.h").write_text("char *get_next_line(int fd);\n")
            (directory / "get_next_line_utils.c").write_text("")
            # a correct gnl, but 8 bytes of stack written 9 times
            (directory / "get_next_line.c").write_text(
                "#include <stdlib.h>\n#include <unistd.h>\n"
                "char *get_next_line(int fd) {\n size_t n = 0, cap = 16; char *buf = malloc(cap), c, tmp[8];\n"
                " int k8 = 0; if (!buf) return NULL;\n for (;;) {\n  ssize_t k = read(fd, &c, 1);\n"
                "  if (k < 0 || (k == 0 && n == 0)) { free(buf); return NULL; }\n  if (k == 0) break;\n"
                "  if (n + 1 >= cap) { char *b = malloc(cap * 2); if (!b) { free(buf); return NULL; }\n"
                "   for (size_t i = 0; i < n; i++) b[i] = buf[i]; free(buf); buf = b; cap *= 2; }\n"
                "  buf[n++] = c; tmp[k8 % 9] = c; k8++; if (c == '\\n') break;\n }\n"
                " buf[n] = 0; (void)tmp; return buf;\n}\n")
            run = [sys.executable, str(ROOT / "torture.py"), "gnl", str(directory), "--no-checks", "-p", "1",
                   "-f", "42", "--lang", "en", "--no-color"]
            result = subprocess.run(run, capture_output=True, text=True, timeout=300)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("SANITIZERS", result.stdout)
            self.assertIn("get_next_line.c:", result.stdout)
            self.assertIn("stack-buffer-overflow (WRITE of 1 bytes)", result.stdout)
            result = subprocess.run([*run, "--no-sanitize"], capture_output=True, text=True, timeout=300)
            self.assertNotIn("SANITIZERS", result.stdout)


if __name__ == "__main__":
    unittest.main()
