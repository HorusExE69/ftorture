"""Tests for the unified Python rendering & explanation backend."""
from contextlib import redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest

from ftorture.checks import CheckReport
from ftorture.renderer import Renderer
from ftorture.runtime import Options


class RendererTests(unittest.TestCase):
    def test_consumes_c_json_events_and_renders_unified_result_box(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            checks_file = root / "checks.txt"
            log_path = root / "ftorture.log"
            report = CheckReport()
            report.section("STRUCTURE")
            report.check("OK", "Extra files", "none")
            report.prototype("ft_strlen", "OK", "size_t ft_strlen(const char *s)", "")
            report.end_prototypes()
            report.write(checks_file)

            renderer = Renderer(
                Options(directory=root, lang="en", no_color=True, efficiency=True, verbose=True),
                log_path,
                repro_prefix=f"torture libft {root}",
            )
            buf = io.StringIO()
            with redirect_stdout(buf):
                renderer.render_checks(checks_file)
                renderer.consume_c_event({"type": "part", "part": 1, "title": "PART 1 · libc functions", "short": "libc"})
                renderer.consume_c_event({"type": "suite_start", "key": "ft_strlen", "label": "ft_strlen",
                                          "part": 1, "short": "libc", "missing": False, "archive": "libft.a", "total": 2})
                renderer.consume_c_event({"type": "test", "index": 1, "res": 0, "glyph": "✔"})
                renderer.consume_c_event({"type": "test", "index": 2, "res": 1, "glyph": "✔"})
                renderer.consume_c_event({
                    "type": "suite_end", "key": "ft_strlen", "label": "ft_strlen", "part": 1,
                    "pass": 2, "fail": 0, "spec": 0, "crash_eq": 1, "total": 2, "missing": False,
                    "eff": {"label": "ft_strlen", "pct": 92, "ideal": 1e-6, "real": 1.08e-6,
                            "bound": False, "score": False},
                })
                renderer.consume_c_event({
                    "type": "hw", "iters": 1e-9, "scan": 1e-9, "copy": 1e-9, "store": 1e-9,
                    "cmp": 1e-9, "calls": 1e-9, "ops": 1e-9, "digits": 1e-9, "nodes": 1e-9,
                    "allocs": 2e-8, "big_allocs": 1e-7, "sys": 5e-7, "rbytes": 1e-9,
                })
                status = renderer.finish()

            output = buf.getvalue()
            self.assertEqual(status, 0)
            self.assertIn("▶ STRUCTURE", output)
            self.assertIn("Prototypes", output)
            self.assertIn("1/1 matching", output)
            self.assertIn("ft_strlen", output)
            self.assertIn("⚡ 92%", output)
            self.assertIn("P1 libc", output)
            self.assertIn("TESTS  2 ✔  0 ✘  0 ▲  / 2", output)
            self.assertIn("CHECKS 2 ✔  0 ✘  0 ▲  protos 1/1", output)
            self.assertIn("EFFICIENCY", output)
            self.assertIn("██████  ██  ██", output)
            self.assertIn("TOTAL: 2 ok, 0 failed", log_path.read_text(encoding="utf-8"))
