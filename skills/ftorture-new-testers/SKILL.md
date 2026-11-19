---
name: ftorture-new-testers
description: Extend ftorture's Python project registry and native subject checks with reliable C suites for additional 42 projects, including build strategies and regression tests.
---

# Add a project tester

Use this skill when changing **ftorture**, not a student's submission. Installation, CLI, builds, checks, and pass coordination are Python-native; the process-isolated test engine and suites remain C. Read the exact subject/version first. Do not reuse another project's rules merely because its build looks similar.

## Architecture map

| Component | Responsibility |
|---|---|
| `ftorture/cli.py` | Argument validation, dependency checks, checkout lock, lifecycle and interruption handling |
| `ftorture/projects/base.py` | `Project` metadata and `validate`, `checks`, `run`, `cleanup` hooks |
| `ftorture/projects/__init__.py` | Explicit `PROJECTS` registry, aliases and header-based detection; also drives the menu |
| `ftorture/registry.py` | Unified registry, collision validation, bundled detection and custom discovery for CLI/TUI |
| `ftorture/projects/custom.py` | Versioned user manifests and command-suite lifecycle, separate from native C checks |
| `ftorture/projects/archive.py` | Makefile/archive building and linking; compare `libft.py`/`printf.py` |
| `ftorture/projects/gnl.py` | Example source-only strategy with multiple compiled test passes |
| `ftorture/runtime.py` | `Options`, `Context`, subprocess cancellation, paths, compiler flags and C-engine arguments |
| `ftorture/language.py` | English/French selection from locale and complete-message selection |
| `ftorture/checks.py` | `CheckSession` probes/localized messages and delimiter-safe `CheckReport` records |
| `ftorture/subject/` | Native file, README, norm, include-use, symbol, prototype and project-specific checks |
| `install.py` | Managed launcher, safe update, confirmed `--delete --confirm` uninstall, shell detection and consent-based PATH configuration |
| `src/zft.h`, `src/project.h` | C test macros/helpers and suite descriptor contract |
| `src/engine.c`, `src/memtrack.c` | Forked execution, reference comparison, allocation instrumentation and reports |

## Integrate the project

1. Extract mandatory/bonus files, prototypes, allowed functions, flags, behavior, resource limits, and undefined cases from the subject. Define the oracle and which cases are speculative. Executable-based or interactive projects may need a new build/capture strategy; the existing archive strategy is not a universal harness.
2. Add `ftorture/projects/<key>.py` with a `Project` subclass and a `PROJECT` instance. Set a unique stable key, name, header, subject version, valid `parts`, aliases, `tools`, and optional `check_tools` (required only when checks run). Declare `requires_compiler=False` for command-only strategies and `requires_makefile=True` when path validation needs a Makefile (`ArchiveProject` already sets it). Import/register the instance in `PROJECTS`; retain deliberate detection priority in `Registry.detect` where headers overlap. No CLI/menu branches should be needed for an ordinary registered project.
3. Call `super().validate(ctx)` before additional validation. Implement `checks(ctx)` with the subject's own policy; the base method intentionally fails rather than pretending checks exist. Implement `run(ctx) -> int`; put cleanup in `cleanup(ctx)`, which the CLI calls in `finally`, including after errors/interruption.
4. For archives, extend `ArchiveProject`, configure `archive`, `source_dir`, and `symbol_prefix` (default `ft_`), then use `build_archive`, `link`, and `ctx.tester`. Override `extra_archives` for linked dependencies. For source-only projects, use `ctx.compile`/`require` and explicit passes as in GNL. Pass argument lists, never interpolated command strings; use `ctx.cc` to preserve compiler arguments.
5. Keep artifacts under `ctx.build`; use `ctx.root` for tester resources and `ctx.options.directory` for student files. `ctx.engine_args`/`tester` forward language, seed, flags, report paths and filters; do not reconstruct them unnecessarily. Multi-pass runs must carry `ctx.stats` with `--stats-out`/`--stats-in`, display checks once, and print one final summary. Translate project-level filters to suite keys when necessary (GNL uses `function_filter=False`). Never report skipped bonus as passed.

## Implement native checks

Use `CheckSession(ctx)` and persist `session.report.write(ctx.checks_file)` in `finally`. `session.capture` returns `(status, output)` and saves numbered diagnostics; `session.compiler` writes and compiles a C probe. `session.check` selects complete English/French labels and details. Do not translate user data or generated source.

Reuse `check_files(session, allowed_predicate)`, `check_readme`, `check_norm`, `IncludeAnalysis(session).run()`, and `check_symbols` from `ftorture/subject/` with explicit subject policies. The existing `allowed_path` and archive/GNL check orchestrators encode current projects, not arbitrary new subjects. If using `check_prototypes`, supply `protos/<key>.txt` entries as `name|function-pointer type|displayed prototype`; `linked_list=True` is specifically libft's layout requirement. Include-use analysis is heuristic: unresolved headers must not be invented into failures.

`CheckReport` writes engine records through `section`, `check` (`OK`, `KO`, `WARN`, `SKIP`), `detail`, `prototype`, and `end_prototypes`; do not hand-concatenate delimiters. Missing or wrong requirements are check failures, not operational exceptions. Use `RunnerError` for an inability to build/run/check, and preserve status semantics: `0` pass, `1` tests/checks failed, `2` operational error, `130` interruption.

## Write and link C suites

For personal command/script tests rather than an official C tester, prefer a
version-1 manifest in `${XDG_CONFIG_HOME:-$HOME/.config}/ftorture/tests/`.
Follow `docs/custom-tests.md` and `examples/custom-tests/`; no ftorture source
edits are needed. These suites are deliberately namespaced `custom-<key>`, marked
`[CUSTOM]` in the original menu, and never auto-detected or presented as subject
validation. Discovery must remain data-only. Validate argument arrays/placeholders,
never implicitly invoke a shell, and use the shared cancellation/timeout lifecycle.
Do not promise C memory instrumentation for plain command suites. Regression tests
live in `tests/test_custom_tests.py` and custom-menu PTY coverage in `tests/test_tui.py`.

- Add `src/<key>/proj.c` defining exactly one `g_proj` and suites with stable keys, labels, part numbers, and student function addresses. Weak declarations let missing symbols be reported; archive symbols must still be force-linked via the correct prefix. Audit the engine before expanding it: part arrays currently allow parts 1–3, statistics storage is bounded, and localization contains project-specific assumptions.
- Put tests in `src/<key>/t_*.c`. Match each `TEST` suite key to the descriptor. Use `SPEC_TEST` for non-required behavior, `VS`/`VS_SPEC` with an independent justified reference, and `MTEST` for allocation failures. For comparisons, use `PICK(student, reference)` and `OUT(...)` on both reference paths; libc is not an oracle for every subject requirement.
- Record `INPUT(...)` before risky calls. Assert exact values/bytes with `CHECK`, `EQ_INT`, `EQ_SZ`, `EQ_STR`, or `EQ_MEM`. Capture bytes **and** return values for output projects; see `src/printf/pf.h`. Use `gstr`/`gmem`/`gbuf` and `alloc_size` when relevant; free allocations and close descriptors. Use `XFREE` when an allocation may originate from either reference path.
- Bracket only relevant student allocations with `ARM()`/`DISARM()` in `MTEST`; failure replays must not crash or leak. Use `zrand()`/`--seed` for deterministic fuzzing, not timing-dependent randomness. Link the engine, memory tracker, suite sources and student objects with appropriate wrappers; current suites wrap `malloc`/`free`, and GNL additionally wraps `read`.

## Validate and document

```bash
python3 -m unittest discover -s tests -v
torture --list-projects
torture <key> /path/to/known-good-project --no-norm
```

For migration parity use `python3 tests/compare_legacy_libft.py /path/to/libft`.
It compares legacy Bash and Python behavior on independent temporary copies,
including all 43 function summaries; do not run it concurrently with integration
tests. See `docs/validation.md` for the reference revision, observed results, and
the distinction between behavioral parity and native subject-check validation.
User-facing commands must use the installed Python launcher `~/.local/bin/torture`;
do not add shell wrappers or require users to run from the ftorture checkout.
Direct Python entry points are retained for internal tests and development only.

Add native-check regressions in `tests/test_subject_checks.py` and real-engine integration coverage in `tests/test_python_runner.py`, or focused new test modules. Use temporary student fixtures. Cover known-good and broken behavior, wrong/missing symbols/prototypes, build errors, complete/partial bonus support, filters/parts, speculative mode, repeatable seeds, language, spaces in paths, and interruption cleanup. Run full mandatory/bonus suites as well as focused tests. Tests overwrite shared checkout artifacts/reports; run serially. Update both READMEs with the subject version, commands and limitations. Never weaken an oracle to accommodate one student's code.
