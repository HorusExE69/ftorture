# Validation

Run tests serially: real-engine integration tests share checkout build artifacts
and overwrite `ftorture.log`.

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q ftorture tests examples install.py torture.py
git diff --check
```

Coverage includes the C engine's good/broken fixtures and mandatory/bonus passes,
native subject checks, cancellation/cleanup, installer migration/collisions,
consent-based shell configuration, confirmed uninstall, manifest validation,
custom filtering/parts/speculative verdicts/timeouts, and real PTY interaction.
The original French pixel banner also has a fixed rendering regression test.

## Original Bash versus Python

```bash
python3 tests/compare_legacy_libft.py ~/projects/42-cursus/libft --legacy-ref 9d3adcc
```

This exports the legacy revision and makes independent temporary copies of the
student directory. Both runners execute the full libft behavioral suite with
seed 42, French output, and no colors. It compares exit status, all 43 per-function
summaries, and total verdict counts. The original student directory is never the
build target. Temporary files are removed afterward. The Python run overwrites
the checkout's usual `ftorture.log`; do not run it alongside other tests.

The migration was checked against `~/projects/42-cursus/libft` with the following
identical legacy/Python results:

```text
exit status: 0
TOTAL: 252 ok, 0 ko, 25 spéculatifs, 0 absentes, 0 vérifs KO -> OK
```

This compares **behavior**, not every historical shell heuristic: subject checks
are deliberately disabled for this comparison and covered separately by native
check regression tests. Current skill guides describe the Python interfaces, not
the old internal shell helpers. No shell entry points are shipped: normal usage
goes through the Python launcher installed at `~/.local/bin/torture`. Direct
Python entry points remain internal development/test interfaces. Bash is used
only when explicitly comparing the historical revision above.
