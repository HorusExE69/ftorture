"""Unit and integration tests for the Python test framework (py00, py01)."""
from pathlib import Path
import tempfile
import unittest

from ftorture.cli import main
from ftorture.projects import detect, find


GOOD_PY00 = {
    "ex0/ft_hello_garden.py": (
        "def ft_hello_garden() -> None:\n"
        "    print(\"Hello, Garden Community!\")\n"
    ),
    "ex1/ft_garden_name.py": (
        "def ft_garden_name() -> None:\n"
        "    name = input(\"Enter garden name: \")\n"
        "    print(f\"Garden: {name}\")\n"
        "    print(\"Status: Growing well!\")\n"
    ),
    "ex2/ft_plot_area.py": (
        "def ft_plot_area() -> None:\n"
        "    length = int(input(\"Enter length: \"))\n"
        "    width = int(input(\"Enter width: \"))\n"
        "    print(f\"Plot area: {length * width}\")\n"
    ),
    "ex3/ft_harvest_total.py": (
        "def ft_harvest_total() -> None:\n"
        "    total = (\n"
        "        int(input(\"Day 1 harvest: \"))\n"
        "        + int(input(\"Day 2 harvest: \"))\n"
        "        + int(input(\"Day 3 harvest: \"))\n"
        "    )\n"
        "    print(f\"Total harvest: {total}\")\n"
    ),
    "ex4/ft_plant_age.py": (
        "def ft_plant_age() -> None:\n"
        "    age = int(input(\"Enter plant age in days: \"))\n"
        "    if age > 60:\n"
        "        print(\"Plant is ready to harvest!\")\n"
        "    else:\n"
        "        print(\"Plant needs more time to grow.\")\n"
    ),
    "ex5/ft_water_reminder.py": (
        "def ft_water_reminder() -> None:\n"
        "    days = int(input(\"Days since last watering: \"))\n"
        "    if days > 2:\n"
        "        print(\"Water the plants!\")\n"
        "    else:\n"
        "        print(\"Plants are fine\")\n"
    ),
    "ex6/ft_count_harvest_iterative.py": (
        "def ft_count_harvest_iterative() -> None:\n"
        "    days = int(input(\"Days until harvest: \"))\n"
        "    for day in range(1, days + 1):\n"
        "        print(f\"Day {day}\")\n"
        "    print(\"Harvest time!\")\n"
    ),
    "ex6/ft_count_harvest_recursive.py": (
        "def ft_count_harvest_recursive() -> None:\n"
        "    days = int(input(\"Days until harvest: \"))\n"
        "\n"
        "    def count(current: int) -> None:\n"
        "        if current > days:\n"
        "            print(\"Harvest time!\")\n"
        "            return\n"
        "        print(f\"Day {current}\")\n"
        "        count(current + 1)\n"
        "\n"
        "    count(1)\n"
    ),
    "ex7/ft_seed_inventory.py": (
        "def ft_seed_inventory(seed_type: str, quantity: int, unit: str) -> None:\n"
        "    label = seed_type.capitalize()\n"
        "    if unit == \"packets\":\n"
        "        print(f\"{label} seeds: {quantity} packets available\")\n"
        "    elif unit == \"grams\":\n"
        "        print(f\"{label} seeds: {quantity} grams total\")\n"
        "    elif unit == \"area\":\n"
        "        print(f\"{label} seeds: covers {quantity} square meters\")\n"
        "    else:\n"
        "        print(\"Unknown unit type\")\n"
    ),
}


GOOD_PY01 = {
    "ex0/ft_garden_intro.py": (
        "if __name__ == \"__main__\":\n"
        "    name: str = \"Rose\"\n"
        "    height: int = 25\n"
        "    age: int = 30\n"
        "    print(\"=== Welcome to My Garden ===\")\n"
        "    print(f\"Plant: {name}\")\n"
        "    print(f\"Height: {height}cm\")\n"
        "    print(f\"Age: {age} days\")\n"
        "    print(\"=== End of Program ===\")\n"
    ),
    "ex1/ft_garden_data.py": (
        "class Plant:\n"
        "    def __init__(self, name: str, height: int, age: int) -> None:\n"
        "        self.name = name\n"
        "        self.height = height\n"
        "        self.age = age\n"
        "\n"
        "    def show(self) -> None:\n"
        "        print(f\"{self.name}: {self.height}cm, {self.age} days old\")\n"
        "\n"
        "\n"
        "if __name__ == \"__main__\":\n"
        "    for plant in (\n"
        "        Plant(\"Rose\", 25, 30),\n"
        "        Plant(\"Sunflower\", 80, 45),\n"
        "        Plant(\"Cactus\", 15, 120),\n"
        "    ):\n"
        "        plant.show()\n"
    ),
    "ex2/ft_plant_growth.py": (
        "class Plant:\n"
        "    def __init__(self, name: str, height: float, days: int) -> None:\n"
        "        self.name = name\n"
        "        self.height = height\n"
        "        self.days = days\n"
        "\n"
        "    def grow(self) -> None:\n"
        "        self.height = round(self.height + 0.8, 1)\n"
        "\n"
        "    def age(self) -> None:\n"
        "        self.days += 1\n"
        "\n"
        "    def show(self) -> None:\n"
        "        print(f\"{self.name}: {self.height}cm, {self.days} days old\")\n"
        "\n"
        "\n"
        "if __name__ == \"__main__\":\n"
        "    rose = Plant(\"Rose\", 25.0, 30)\n"
        "    for day in range(1, 8):\n"
        "        rose.grow()\n"
        "        rose.age()\n"
        "        print(f\"Day {day}\")\n"
        "        rose.show()\n"
    ),
    "ex3/ft_plant_factory.py": (
        "class Plant:\n"
        "    def __init__(self, name: str, height: float, days: int) -> None:\n"
        "        self.name = name\n"
        "        self.height = height\n"
        "        self.days = days\n"
        "\n"
        "    def show(self) -> None:\n"
        "        print(f\"{self.name}: {self.height}cm, {self.days} days old\")\n"
        "\n"
        "\n"
        "if __name__ == \"__main__\":\n"
        "    for plant in (\n"
        "        Plant(\"Rose\", 25.0, 30),\n"
        "        Plant(\"Oak\", 200.0, 365),\n"
        "        Plant(\"Cactus\", 5.0, 90),\n"
        "        Plant(\"Sunflower\", 80.0, 45),\n"
        "        Plant(\"Fern\", 15.0, 120),\n"
        "    ):\n"
        "        plant.show()\n"
    ),
    "ex4/ft_garden_security.py": (
        "class Plant:\n"
        "    def __init__(self, name: str, height: float, age: int) -> None:\n"
        "        self.name = name\n"
        "        self._height = height if height >= 0 else 0.0\n"
        "        self._age = age if age >= 0 else 0\n"
        "\n"
        "    def set_height(self, height: float) -> None:\n"
        "        if height < 0:\n"
        "            print(\"Error: negative height\")\n"
        "            return\n"
        "        self._height = height\n"
        "\n"
        "    def set_age(self, age: int) -> None:\n"
        "        if age < 0:\n"
        "            print(\"Error: negative age\")\n"
        "            return\n"
        "        self._age = age\n"
        "\n"
        "    def get_height(self) -> float:\n"
        "        return self._height\n"
        "\n"
        "    def get_age(self) -> int:\n"
        "        return self._age\n"
        "\n"
        "\n"
        "if __name__ == \"__main__\":\n"
        "    print(\"=== Garden Security System ===\")\n"
        "    rose = Plant(\"Rose\", 15.0, 10)\n"
        "    rose.set_height(25)\n"
        "    rose.set_height(-5)\n"
        "    print(rose.get_height(), rose.get_age())\n"
    ),
    "ex5/ft_plant_types.py": (
        "class Plant:\n"
        "    def __init__(self, name: str, height: float, age: int) -> None:\n"
        "        self.name = name\n"
        "        self.height = height\n"
        "        self.age = age\n"
        "\n"
        "    def show(self) -> None:\n"
        "        print(f\"{self.name}: {self.height}cm, {self.age} days old\")\n"
        "\n"
        "\n"
        "class Flower(Plant):\n"
        "    def __init__(\n"
        "        self, name: str, height: float, age: int, color: str\n"
        "    ) -> None:\n"
        "        super().__init__(name, height, age)\n"
        "        self.color = color\n"
        "\n"
        "    def bloom(self) -> None:\n"
        "        print(f\"{self.name} is blooming\")\n"
        "\n"
        "\n"
        "class Tree(Plant):\n"
        "    def __init__(\n"
        "        self, name: str, height: float, age: int, trunk: float\n"
        "    ) -> None:\n"
        "        super().__init__(name, height, age)\n"
        "        self.trunk_diameter = trunk\n"
        "\n"
        "    def produce_shade(self) -> None:\n"
        "        print(f\"{self.name} produces shade\")\n"
        "\n"
        "\n"
        "class Vegetable(Plant):\n"
        "    def __init__(\n"
        "        self, name: str, height: float, age: int, season: str\n"
        "    ) -> None:\n"
        "        super().__init__(name, height, age)\n"
        "        self.harvest_season = season\n"
        "        self.nutritional_value = 0\n"
        "\n"
        "\n"
        "if __name__ == \"__main__\":\n"
        "    f = Flower(\"Rose\", 15.0, 10, \"red\")\n"
        "    t = Tree(\"Oak\", 200.0, 365, 5.0)\n"
        "    v = Vegetable(\"Tomato\", 5.0, 10, \"April\")\n"
        "    f.show()\n"
        "    f.bloom()\n"
        "    t.show()\n"
        "    t.produce_shade()\n"
        "    v.show()\n"
    ),
    "ex6/ft_garden_analytics.py": (
        "class Plant:\n"
        "    class Stats:\n"
        "        def __init__(self) -> None:\n"
        "            self._grow = 0\n"
        "            self._age = 0\n"
        "            self._show = 0\n"
        "\n"
        "    def __init__(self, name: str, height: float, age: int) -> None:\n"
        "        self.name = name\n"
        "        self.height = height\n"
        "        self.age = age\n"
        "        self.stats = self.Stats()\n"
        "\n"
        "    @staticmethod\n"
        "    def is_older_than_year(days: int) -> bool:\n"
        "        return days > 365\n"
        "\n"
        "    @classmethod\n"
        "    def anonymous(cls) -> \"Plant\":\n"
        "        return cls(\"Unknown plant\", 0.0, 0)\n"
        "\n"
        "\n"
        "class Flower(Plant):\n"
        "    def __init__(\n"
        "        self, name: str, height: float, age: int, color: str\n"
        "    ) -> None:\n"
        "        super().__init__(name, height, age)\n"
        "        self.color = color\n"
        "\n"
        "\n"
        "class Tree(Plant):\n"
        "    def __init__(\n"
        "        self, name: str, height: float, age: int, trunk: float\n"
        "    ) -> None:\n"
        "        super().__init__(name, height, age)\n"
        "        self.trunk = trunk\n"
        "\n"
        "\n"
        "class Seed(Flower):\n"
        "    def __init__(\n"
        "        self, name: str, height: float, age: int, color: str, seeds: int\n"
        "    ) -> None:\n"
        "        super().__init__(name, height, age, color)\n"
        "        self.seeds = seeds\n"
        "\n"
        "\n"
        "def display_stats(plant: Plant) -> None:\n"
        "    print(f\"Stats for {plant.name}\")\n"
        "\n"
        "\n"
        "if __name__ == \"__main__\":\n"
        "    print(\"=== Garden statistics ===\")\n"
        "    print(Plant.is_older_than_year(30))\n"
        "    print(Plant.is_older_than_year(400))\n"
        "    s = Seed(\"Sunflower\", 80.0, 45, \"yellow\", 42)\n"
        "    a = Plant.anonymous()\n"
        "    display_stats(s)\n"
        "    display_stats(a)\n"
    ),
}


def write_tree(root: Path, files: dict[str, str]) -> None:
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


class PythonProjectsTests(unittest.TestCase):
    def test_registry_lookup_and_autodetection(self):
        self.assertEqual(find("py00").key, "py00")
        self.assertEqual(find("python-module-00").key, "py00")
        self.assertEqual(find("py01").key, "py01")
        self.assertEqual(find("python-module-01").key, "py01")
        with tempfile.TemporaryDirectory() as tmp:
            p0 = Path(tmp) / "m0"
            p1 = Path(tmp) / "m1"
            write_tree(p0, {"ex0/ft_hello_garden.py": GOOD_PY00["ex0/ft_hello_garden.py"]})
            write_tree(p1, {"ex0/ft_garden_intro.py": GOOD_PY01["ex0/ft_garden_intro.py"]})
            self.assertEqual(detect(p0).key, "py00")
            self.assertEqual(detect(p1).key, "py01")

    def test_py00_good_submission_passes_and_leaves_no_pycache(self):
        with tempfile.TemporaryDirectory(prefix="py00 good ") as tmp:
            root = Path(tmp)
            write_tree(root, GOOD_PY00)
            status = main([str(root), "--lang", "en", "--no-color"])
            self.assertEqual(status, 0)
            self.assertEqual(list(root.rglob("__pycache__")), [])

    def test_py00_filters_chill_and_failure_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            broken = dict(GOOD_PY00)
            broken["ex0/ft_hello_garden.py"] = "def ft_hello_garden():\n    print('Wrong')\n"
            broken["extra.txt"] = "leftover\n"
            write_tree(root, broken)
            # Filtered to ex7 passes tests, but extra.txt makes checks KO
            self.assertEqual(main(["py00", str(root), "-f", "ex7", "--no-color"]), 1)
            # Chill mode downgrades extra.txt KO to warning -> exit 0
            self.assertEqual(main(["py00", str(root), "-f", "ex7", "-c", "--no-color"]), 0)
            # Strict + chill makes warning fail again
            self.assertEqual(main(["py00", str(root), "-f", "ex7", "-c", "-s", "--no-color"]), 1)
            # ex0 fails behavioral test even without checks
            self.assertEqual(main(["py00", str(root), "-f", "ex0", "--no-checks", "-v", "--no-color"]), 1)
            # Unknown filter is operational error
            self.assertEqual(main(["py00", str(root), "-f", "nonexistent", "--no-color"]), 2)

    def test_py00_detects_top_level_code_and_unauthorized_builtin(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            broken = dict(GOOD_PY00)
            broken["ex0/ft_hello_garden.py"] = (
                "def ft_hello_garden() -> None:\n"
                "    print(len('hi'))\n"
                "\n"
                "if __name__ == '__main__':\n"
                "    ft_hello_garden()\n"
            )
            write_tree(root, broken)
            self.assertEqual(main(["py00", str(root), "-f", "ex0", "--no-norm", "--no-color"]), 1)

    def test_py01_good_submission_passes(self):
        with tempfile.TemporaryDirectory(prefix="py01 good ") as tmp:
            root = Path(tmp)
            write_tree(root, GOOD_PY01)
            status = main([str(root), "--lang", "fr", "--no-color"])
            self.assertEqual(status, 0)
            self.assertEqual(list(root.rglob("__pycache__")), [])

    def test_py01_detects_mangling_and_missing_annotations(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            broken = dict(GOOD_PY01)
            broken["ex4/ft_garden_security.py"] = (
                "class Plant:\n"
                "    def __init__(self, name, height, age):\n"
                "        self.__height = height\n"
                "        self.__age = age\n"
                "    def set_height(self, h): self.__height = h\n"
                "    def set_age(self, a): self.__age = a\n"
                "    def get_height(self): return self.__height\n"
                "    def get_age(self): return self.__age\n"
            )
            write_tree(root, broken)
            self.assertEqual(main(["py01", str(root), "-f", "ex4", "--no-checks", "--no-color"]), 1)

    def test_repro_rejected_for_python_projects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_tree(root, {"ex0/ft_hello_garden.py": GOOD_PY00["ex0/ft_hello_garden.py"]})
            self.assertEqual(main(["py00", str(root), "--repro", "t_part1.c#0", "--no-color"]), 2)


class StrictTypingTests(unittest.TestCase):
    def test_every_function_typed_and_generics_parametrized(self):
        import ast
        from ftorture.subject.python import annotation_issues
        source = (
            "def ok(a: int, *b: str, **c: float) -> list[int]:\n"
            "    def inner(x: int) -> int:\n        return x\n    return [inner(a)]\n"
            "def bare(a: list, b: dict[str, int]) -> dict:\n    return {}\n"
            "def untyped(a, b: int):\n    pass\n"
            "class A:\n    def m(self, n) -> None:\n        pass\n"
            "values: list = []\n"
            "good: dict[str, list[int]] = {}\n"
        )
        issues = annotation_issues("ex0/f.py", ast.parse(source))
        text = "\n".join(issues)
        self.assertNotIn("ok()", text)
        self.assertNotIn("inner()", text)
        self.assertIn("bare(): list without its type parameters", text)
        self.assertIn("bare(): dict without its type parameters", text)
        self.assertIn("untyped() untyped param(s): a", text)
        self.assertIn("untyped() missing return type", text)
        self.assertIn("m() untyped param(s): n", text)
        self.assertIn("ex0/f.py:12 list without its type parameters", text)
        self.assertNotIn(":13", text)

    def test_mypy_runs_in_strict_mode(self):
        import inspect
        from ftorture.subject import python
        source = inspect.getsource(python.check_mypy)
        self.assertEqual(source.count('"--strict"'), 2)
