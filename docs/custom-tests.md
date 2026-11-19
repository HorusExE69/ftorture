# User-owned test suites

Custom suites are an extension interface, not official 42 subject checks. They
appear after the bundled projects in the original menu, in cyan with `[CUSTOM]`.
The bundled LIBFT/FT_PRINTF/GNL shortcuts remain `1`/`2`/`3`. Use arrow keys for
any number of entries; number shortcuts work for the first nine.

## Quick start

After `python3 install.py`, try the included, read-only example using the installed
command from any directory (adjust `~/ftorture` to your checkout's location):

```bash
torture --custom-tests-dir ~/ftorture/examples/custom-tests --list-projects
torture --custom-tests-dir ~/ftorture/examples/custom-tests custom-readme /path/to/project -v
torture --custom-tests-dir ~/ftorture/examples/custom-tests
```

To make your tests available by default, copy `examples/custom-tests/readme.json`
and `check_readme.py` into `${XDG_CONFIG_HOME:-$HOME/.config}/ftorture/tests/`.
No changes to ftorture's source or registry are necessary. Edit the copied files,
not the bundled example. `--custom-tests-dir DIR` replaces that discovery location
for one invocation. Only top-level `*.json` files are loaded, in filename order.
Discovery reads and validates manifests; it never imports or executes their code.

Custom keys are namespaced: a manifest with `"key": "readme"` is selected as
`custom-readme`. Custom suites are never automatically chosen by header detection.
Duplicate keys or aliases and invalid manifests produce an error with their path.

## Manifest version 1

```json
{
  "version": 1,
  "key": "my-suite",
  "name": "My extra tests",
  "header": "libft.h",
  "timeout": 5,
  "build": [
    ["make", "-C", "{directory}"],
    ["cc", "{tests_dir}/my_test.c", "{directory}/libft.a", "-o", "{build}/my-test"]
  ],
  "tests": [
    {"name": "basic", "command": ["{build}/my-test"], "part": 1},
    {"name": "edge", "command": ["{build}/my-test", "edge"], "part": 2, "speculative": true}
  ],
  "cleanup": [
    ["make", "-C", "{directory}", "clean"]
  ]
}
```

| Field | Meaning |
|---|---|
| `version` | Required integer `1` |
| `key` | Required lowercase key: initial letter, then letters/digits/hyphens; at most 48 characters |
| `name` | Required printable menu label |
| `header` | Optional relative path to require in the selected project; no `..` or absolute path |
| `timeout` | Positive seconds per test command, default `3`; CLI `--timeout` overrides it |
| `build` / `cleanup` | Optional arrays of command arrays; run in order |
| `tests` | Required nonempty array of test objects |
| Test `name` | Unique printable name, without commas; used by `-f name,other` |
| Test `command` | Required nonempty array of nonempty argument strings |
| Test `part` | Integer `1`–`3`, default `1`; selected by `-p` |
| Test `expected_exit` | Expected exit code, default `0`; `124` is reserved for timeout |
| Test `speculative` | Boolean, default false; failures warn (`▲`) unless `-s` is set |

Unknown fields are rejected to catch typos. Commands are argument arrays, not
shell strings: there is no implicit shell, quoting, expansion, pipe, or redirection.
Spaces in paths are preserved. Use separate script files for complex test logic.

Available placeholders in command arguments:

- `{python}`: the running Python interpreter.
- `{directory}`: the selected project directory (absolute).
- `{tests_dir}`: the manifest's directory (absolute).
- `{build}`: `build/custom-<key>/` in the checkout (absolute).
- `{root}`: the ftorture checkout (absolute).
- `{seed}`: the numeric seed.

Escape literal braces as `{{` and `}}`. Unknown placeholders, attribute access,
format specifications, and conversions are rejected.

All commands run with `{build}` as their current directory. The environment also
contains `FTORTURE_DIRECTORY`, `FTORTURE_BUILD`, `FTORTURE_TESTS_DIR`,
`FTORTURE_PROJECT`, `FTORTURE_SEED`, and `FTORTURE_LANG`. `NO_COLOR` is forwarded.

## Results and lifecycle

- Exit `0`: selected tests passed (or only non-strict speculative failures).
- Exit `1`: test failure or timeout; test signals also fail.
- Exit `2`: invalid manifests/options, missing commands, or failed build/cleanup.
- Exit `130`: interruption.

`✔`, `✘`, `▲`, and timeout `T` are shown with `[CUSTOM]` beside each name and a
single final result. `-v` prints captured output. Diagnostics live in
`build/custom-<key>/build-N.log`, `test-N.log`, and `cleanup-N.log`;
`ftorture.log` contains the plain-text report. Runs share the checkout lock.
Reports are replaced on the next run, including by bundled testers.

Cleanup runs after build/test errors and interruption, not before validation or
dependency/lock failures. Timeout/interruption stops the command's process group
before cleanup. Build and cleanup commands do not inherit the per-test timeout.
`--no-checks`, `--no-norm`, and `--no-hidden` affect bundled subject checks only;
the custom options screen therefore shows only strict mode and verbose.
Custom suites need no C tools unless their own commands use them.

**Only run trusted manifests and scripts.** They execute with your permissions,
are not sandboxed, and can modify your project if their commands do so. Custom
commands do not automatically receive the C engine's guarded memory, leak
detection, malloc-failure injection, or libc comparisons. For those capabilities,
add a native project/C suite via the
[tester authoring skill](../skills/ftorture-new-testers/SKILL.md).
