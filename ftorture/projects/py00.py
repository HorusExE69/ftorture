"""python-module-00 (Growing Code, v3.0): Python fundamentals through garden data."""
import ast
import json
from pathlib import Path

from .python import (PyOutcome, PySuite, PyTestCase, PythonProject,
                     eval_module_code, expect_json_outcome)
from ..runtime import Context
from ..subject.python import ExerciseSpec

SPECS: tuple[ExerciseSpec, ...] = (
    ExerciseSpec("ex0", "ex0", ("ft_hello_garden.py",),
                 authorized=frozenset({"print"}), expected_functions=("ft_hello_garden",)),
    ExerciseSpec("ex1", "ex1", ("ft_garden_name.py",),
                 authorized=frozenset({"input", "print"}), expected_functions=("ft_garden_name",)),
    ExerciseSpec("ex2", "ex2", ("ft_plot_area.py",),
                 authorized=frozenset({"input", "int", "print"}), expected_functions=("ft_plot_area",)),
    ExerciseSpec("ex3", "ex3", ("ft_harvest_total.py",),
                 authorized=frozenset({"input", "int", "print"}), expected_functions=("ft_harvest_total",)),
    ExerciseSpec("ex4", "ex4", ("ft_plant_age.py",),
                 authorized=frozenset({"input", "int", "print"}), expected_functions=("ft_plant_age",)),
    ExerciseSpec("ex5", "ex5", ("ft_water_reminder.py",),
                 authorized=frozenset({"input", "int", "print"}), expected_functions=("ft_water_reminder",)),
    ExerciseSpec("ex6", "ex6", ("ft_count_harvest_iterative.py", "ft_count_harvest_recursive.py"),
                 authorized=frozenset({"input", "int", "print", "range"}), allow_helpers=True,
                 expected_functions=("ft_count_harvest_iterative", "ft_count_harvest_recursive")),
    ExerciseSpec("ex7", "ex7", ("ft_seed_inventory.py",),
                 authorized=frozenset({"print"}), require_type_hints=True,
                 expected_functions=("ft_seed_inventory",)),
)


def _call_io_test(rel_path: str, func_name: str, stdin_lines: list[str],
                  expected_lines: list[str], *, check_import_silent: bool = False):
    """Build a test runner that imports `rel_path`, mocks input(), and checks printed lines."""
    def runner(ctx: Context, directory: Path, timeout: int) -> PyOutcome:
        code = (
            "import json, builtins\n"
            f"_inputs = iter({stdin_lines!r})\n"
            "_printed = []\n"
            "_orig_print = builtins.print\n"
            "def _mock_input(prompt=''):\n"
            "    try:\n"
            "        return next(_inputs)\n"
            "    except StopIteration:\n"
            "        raise EOFError('too many input() calls')\n"
            "def _mock_print(*args, sep=' ', end='\\n', **kw):\n"
            "    _printed.append(sep.join(str(a) for a in args) + end)\n"
            "builtins.input = _mock_input\n"
            "builtins.print = _mock_print\n"
            f"_fn = getattr(mod, {func_name!r}, None)\n"
            "if not callable(_fn):\n"
            f"    _orig_print(json.dumps({{'ok': False, 'detail': 'missing function {func_name}()'}}))\n"
            "else:\n"
            "    _ret = _fn()\n"
            "    _out = ''.join(_printed).splitlines()\n"
            f"    _exp = {expected_lines!r}\n"
            "    _ok = (_out == _exp and _ret is None)\n"
            "    _detail = '' if _ok else ('function must return None' if _out == _exp else 'output mismatch')\n"
            "    _orig_print(json.dumps({'ok': _ok, 'detail': _detail, "
            "'expected': ' | '.join(_exp), 'actual': ' | '.join(_out)}))\n"
        )
        desc = f"{func_name}()" + (f" stdin={stdin_lines!r}" if stdin_lines else "")
        return expect_json_outcome(ctx, directory, rel_path, code, timeout=timeout, input_desc=desc)
    return runner


def _import_silent_test(rel_path: str):
    def runner(ctx: Context, directory: Path, timeout: int) -> PyOutcome:
        status, stdout, stderr = eval_module_code(ctx, directory, rel_path, "", timeout=timeout)
        if status == 124:
            return PyOutcome(False, f"timeout ({timeout}s)", timed_out=True)
        if status != 0:
            return PyOutcome(False, (stderr.strip().splitlines() or [f"exit {status}"])[-1])
        if stdout:
            return PyOutcome(False, "code executed on import", expected="(no output)", actual=stdout.strip())
        return PyOutcome(True)
    return runner


def _recursion_check(rel_path: str, func_name: str, *, expect_recursive: bool):
    def runner(ctx: Context, directory: Path, timeout: int) -> PyOutcome:
        try:
            tree = ast.parse((directory / rel_path).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, SyntaxError) as exc:
            return PyOutcome(False, str(exc))
        # Check if any function in the module calls itself (direct recursion)
        recursive_funcs: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id == node.name:
                        recursive_funcs.add(node.name)
        has_loop = any(isinstance(n, (ast.For, ast.While)) for n in ast.walk(tree))
        if expect_recursive:
            if recursive_funcs:
                return PyOutcome(True)
            return PyOutcome(False, "no recursive call detected", expected="recursive call", actual="none")
        if has_loop and not recursive_funcs:
            return PyOutcome(True)
        return PyOutcome(False, "expected iterative loop without recursion",
                         expected="for/while loop", actual="recursion" if recursive_funcs else "no loop")
    return runner


def _seed_inventory_test(seed_type: str, quantity: int, unit: str, expected: str):
    def runner(ctx: Context, directory: Path, timeout: int) -> PyOutcome:
        code = (
            "import json, io, contextlib\n"
            "_fn = getattr(mod, 'ft_seed_inventory', None)\n"
            "if not callable(_fn):\n"
            "    print(json.dumps({'ok': False, 'detail': 'missing function ft_seed_inventory()'}))\n"
            "else:\n"
            "    _buf = io.StringIO()\n"
            "    with contextlib.redirect_stdout(_buf):\n"
            f"        _ret = _fn({seed_type!r}, {quantity!r}, {unit!r})\n"
            "    _out = _buf.getvalue().splitlines()\n"
            f"    _exp = [{expected!r}]\n"
            "    _ok = (_out == _exp and _ret is None)\n"
            "    _detail = '' if _ok else ('function must return None' if _out == _exp else 'output mismatch')\n"
            "    print(json.dumps({'ok': _ok, 'detail': _detail, 'expected': _exp[0], 'actual': ' | '.join(_out)}))\n"
        )
        desc = f"ft_seed_inventory({seed_type!r}, {quantity!r}, {unit!r})"
        return expect_json_outcome(ctx, directory, "ex7/ft_seed_inventory.py", code, timeout=timeout, input_desc=desc)
    return runner


def _seed_signature_test():
    def runner(ctx: Context, directory: Path, timeout: int) -> PyOutcome:
        code = (
            "import inspect, json, typing\n"
            "_fn = getattr(mod, 'ft_seed_inventory', None)\n"
            "if not callable(_fn):\n"
            "    print(json.dumps({'ok': False, 'detail': 'missing function ft_seed_inventory()'}))\n"
            "else:\n"
            "    _sig = inspect.signature(_fn)\n"
            "    _params = list(_sig.parameters.values())\n"
            "    _hints = typing.get_type_hints(_fn)\n"
            "    _ret = _hints.get('return', inspect.Signature.empty)\n"
            "    _ok = (len(_params) == 3 "
            "and _hints.get(_params[0].name) is str "
            "and _hints.get(_params[1].name) is int "
            "and _hints.get(_params[2].name) is str "
            "and _ret in (None, type(None)))\n"
            "    print(json.dumps({'ok': _ok, 'detail': '' if _ok else 'signature mismatch', "
            "'expected': '(seed_type: str, quantity: int, unit: str) -> None', 'actual': str(_sig)}))\n"
        )
        return expect_json_outcome(ctx, directory, "ex7/ft_seed_inventory.py", code, timeout=timeout,
                                   input_desc="inspect.signature(ft_seed_inventory)")
    return runner


SUITES: tuple[PySuite, ...] = (
    PySuite("ex0", "ex0 · ft_hello_garden", ("ex0/ft_hello_garden.py",), aliases=("0", "hello"), cases=(
        PyTestCase("silent on import", "silencieux à l'import", _import_silent_test("ex0/ft_hello_garden.py")),
        PyTestCase("prints greeting", "affiche le message d'accueil",
                   _call_io_test("ex0/ft_hello_garden.py", "ft_hello_garden", [], ["Hello, Garden Community!"])),
    )),
    PySuite("ex1", "ex1 · ft_garden_name", ("ex1/ft_garden_name.py",), aliases=("1", "name"), cases=(
        PyTestCase("silent on import", "silencieux à l'import", _import_silent_test("ex1/ft_garden_name.py")),
        PyTestCase("Community Garden", "Community Garden",
                   _call_io_test("ex1/ft_garden_name.py", "ft_garden_name", ["Community Garden"],
                                 ["Garden: Community Garden", "Status: Growing well!"])),
        PyTestCase("custom name", "nom personnalisé",
                   _call_io_test("ex1/ft_garden_name.py", "ft_garden_name", ["42 Lyon"],
                                 ["Garden: 42 Lyon", "Status: Growing well!"])),
    )),
    PySuite("ex2", "ex2 · ft_plot_area", ("ex2/ft_plot_area.py",), aliases=("2", "area"), cases=(
        PyTestCase("5 x 3 = 15", "5 x 3 = 15",
                   _call_io_test("ex2/ft_plot_area.py", "ft_plot_area", ["5", "3"], ["Plot area: 15"])),
        PyTestCase("0 x 10 = 0", "0 x 10 = 0",
                   _call_io_test("ex2/ft_plot_area.py", "ft_plot_area", ["0", "10"], ["Plot area: 0"])),
        PyTestCase("12 x 12 = 144", "12 x 12 = 144",
                   _call_io_test("ex2/ft_plot_area.py", "ft_plot_area", ["12", "12"], ["Plot area: 144"])),
    )),
    PySuite("ex3", "ex3 · ft_harvest_total", ("ex3/ft_harvest_total.py",), aliases=("3", "harvest"), cases=(
        PyTestCase("5 + 8 + 3 = 16", "5 + 8 + 3 = 16",
                   _call_io_test("ex3/ft_harvest_total.py", "ft_harvest_total", ["5", "8", "3"], ["Total harvest: 16"])),
        PyTestCase("0 + 0 + 0 = 0", "0 + 0 + 0 = 0",
                   _call_io_test("ex3/ft_harvest_total.py", "ft_harvest_total", ["0", "0", "0"], ["Total harvest: 0"])),
        PyTestCase("100 + 200 + 300 = 600", "100 + 200 + 300 = 600",
                   _call_io_test("ex3/ft_harvest_total.py", "ft_harvest_total", ["100", "200", "300"],
                                 ["Total harvest: 600"])),
    )),
    PySuite("ex4", "ex4 · ft_plant_age", ("ex4/ft_plant_age.py",), aliases=("4", "age"), cases=(
        PyTestCase("75 days (ready)", "75 jours (prêt)",
                   _call_io_test("ex4/ft_plant_age.py", "ft_plant_age", ["75"], ["Plant is ready to harvest!"])),
        PyTestCase("45 days (grow)", "45 jours (pousser)",
                   _call_io_test("ex4/ft_plant_age.py", "ft_plant_age", ["45"], ["Plant needs more time to grow."])),
        PyTestCase("boundary 60 days", "limite 60 jours",
                   _call_io_test("ex4/ft_plant_age.py", "ft_plant_age", ["60"], ["Plant needs more time to grow."])),
        PyTestCase("boundary 61 days", "limite 61 jours",
                   _call_io_test("ex4/ft_plant_age.py", "ft_plant_age", ["61"], ["Plant is ready to harvest!"])),
    )),
    PySuite("ex5", "ex5 · ft_water_reminder", ("ex5/ft_water_reminder.py",), aliases=("5", "water"), cases=(
        PyTestCase("4 days (water)", "4 jours (arroser)",
                   _call_io_test("ex5/ft_water_reminder.py", "ft_water_reminder", ["4"], ["Water the plants!"])),
        PyTestCase("1 day (fine)", "1 jour (ok)",
                   _call_io_test("ex5/ft_water_reminder.py", "ft_water_reminder", ["1"], ["Plants are fine"])),
        PyTestCase("boundary 2 days", "limite 2 jours",
                   _call_io_test("ex5/ft_water_reminder.py", "ft_water_reminder", ["2"], ["Plants are fine"])),
        PyTestCase("boundary 3 days", "limite 3 jours",
                   _call_io_test("ex5/ft_water_reminder.py", "ft_water_reminder", ["3"], ["Water the plants!"])),
    )),
    PySuite("ex6", "ex6 · ft_count_harvest",
            ("ex6/ft_count_harvest_iterative.py", "ex6/ft_count_harvest_recursive.py"),
            aliases=("6", "count", "ft_count_harvest"), cases=(
        PyTestCase("iterative 5 days", "itératif 5 jours",
                   _call_io_test("ex6/ft_count_harvest_iterative.py", "ft_count_harvest_iterative", ["5"],
                                 ["Day 1", "Day 2", "Day 3", "Day 4", "Day 5", "Harvest time!"])),
        PyTestCase("iterative 1 day", "itératif 1 jour",
                   _call_io_test("ex6/ft_count_harvest_iterative.py", "ft_count_harvest_iterative", ["1"],
                                 ["Day 1", "Harvest time!"])),
        PyTestCase("uses iteration", "utilise l'itération",
                   _recursion_check("ex6/ft_count_harvest_iterative.py", "ft_count_harvest_iterative",
                                    expect_recursive=False)),
        PyTestCase("recursive 5 days", "récursif 5 jours",
                   _call_io_test("ex6/ft_count_harvest_recursive.py", "ft_count_harvest_recursive", ["5"],
                                 ["Day 1", "Day 2", "Day 3", "Day 4", "Day 5", "Harvest time!"])),
        PyTestCase("recursive 1 day", "récursif 1 jour",
                   _call_io_test("ex6/ft_count_harvest_recursive.py", "ft_count_harvest_recursive", ["1"],
                                 ["Day 1", "Harvest time!"])),
        PyTestCase("uses recursion", "utilise la récursion",
                   _recursion_check("ex6/ft_count_harvest_recursive.py", "ft_count_harvest_recursive",
                                    expect_recursive=True)),
    )),
    PySuite("ex7", "ex7 · ft_seed_inventory", ("ex7/ft_seed_inventory.py",), aliases=("7", "seed", "inventory"), cases=(
        PyTestCase("type signature", "signature typée", _seed_signature_test()),
        PyTestCase("packets", "packets",
                   _seed_inventory_test("tomato", 15, "packets", "Tomato seeds: 15 packets available")),
        PyTestCase("grams", "grams",
                   _seed_inventory_test("carrot", 8, "grams", "Carrot seeds: 8 grams total")),
        PyTestCase("area", "area",
                   _seed_inventory_test("lettuce", 12, "area", "Lettuce seeds: covers 12 square meters")),
        PyTestCase("unknown unit", "unité inconnue",
                   _seed_inventory_test("basil", 5, "liters", "Unknown unit type")),
    )),
)

PROJECT = PythonProject(
    key="py00",
    name="python-module-00",
    header="",
    subject="3.0",
    aliases=("python00", "python-module-00", "growing_code"),
    specs=SPECS,
    suites=SUITES,
)
