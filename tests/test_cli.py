"""Тесты интерфейса командной строки."""

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from typing import NamedTuple

from depviz.cli import EXIT_CONFIG_ERROR, EXIT_FETCH_ERROR, EXIT_OK, main
from depviz.config import DEFAULT_REGISTRY_URL, parse_config
from depviz.report import NOT_SET_LABEL, format_config
from tests import DATA_DIRECTORY
from tests.fake_registry import FakeRegistry, FakeResponse, make_packument

SOURCE_DIRECTORY = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"
)


class MainResult(NamedTuple):
    """Результат запуска main: код завершения и перехваченный вывод."""

    code: int
    output: str
    errors: str


def run_direct(package: str, repo_url: str) -> MainResult:
    """Вывести прямые зависимости пакета из репозитория по URL."""
    return run_main(["-p", package, "-r", repo_url, "-s", "direct"])


def run_main(argv: list[str]) -> MainResult:
    """Запустить main и вернуть код завершения, stdout и stderr."""
    out_buffer = io.StringIO()
    err_buffer = io.StringIO()
    with contextlib.redirect_stdout(out_buffer):
        with contextlib.redirect_stderr(err_buffer):
            code = main(argv)
    return MainResult(code, out_buffer.getvalue(), err_buffer.getvalue())


class TestMain(unittest.TestCase):
    """Проверки функции main."""

    def test_prints_all_parameters(self) -> None:
        """Все параметры выводятся в формате ключ-значение."""
        argv = ["-p", "express", "-a", "-f", "test", "-s", "config"]
        result = run_main(argv)
        expected = [
            "package: express",
            f"repo: {DEFAULT_REGISTRY_URL}",
            "test_mode: false",
            "ascii_tree: true",
            "filter: test",
            "show: config",
        ]
        self.assertEqual(result.code, EXIT_OK)
        self.assertEqual(result.output.splitlines(), expected)
        self.assertEqual(result.errors, "")

    def test_unset_filter_has_placeholder(self) -> None:
        """Незаданный фильтр выводится как заглушка."""
        result = run_main(["-p", "express", "-s", "config"])
        placeholder_line = f"filter: {NOT_SET_LABEL}"
        self.assertIn(placeholder_line, result.output.splitlines())

    def test_error_goes_to_stderr(self) -> None:
        """Ошибка пишется в stderr, код завершения ненулевой."""
        result = run_main(["-p", "Bad Name"])
        self.assertEqual(result.code, EXIT_CONFIG_ERROR)
        self.assertEqual(result.output, "")
        self.assertIn("Ошибка", result.errors)


class TestShowDirect(unittest.TestCase):
    """Проверки вывода прямых зависимостей."""

    def test_prints_direct_dependencies(self) -> None:
        """Прямые зависимости выводятся списком по именам."""
        dependencies = {"zeta": "^1.0.0", "alpha": "~2.1.0"}
        responses = {"demo": make_packument("demo", "1.2.3", dependencies)}
        with FakeRegistry(responses) as registry:
            result = run_direct("demo", registry.url)
        expected = [
            "Прямые зависимости demo@1.2.3 (2):",
            "  alpha (~2.1.0)",
            "  zeta (^1.0.0)",
        ]
        self.assertEqual(result.code, EXIT_OK)
        self.assertEqual(result.output.splitlines(), expected)

    def test_package_without_dependencies(self) -> None:
        """Для пакета без зависимостей выводится соответствующая строка."""
        responses = {"leaf": make_packument("leaf", "0.1.0", {})}
        with FakeRegistry(responses) as registry:
            result = run_direct("leaf", registry.url)
        self.assertEqual(result.code, EXIT_OK)
        self.assertEqual(
            result.output.strip(), "Прямые зависимости leaf@0.1.0: отсутствуют"
        )

    def test_unknown_package_gives_fetch_error(self) -> None:
        """Отсутствующий пакет дает код ошибки получения данных."""
        with FakeRegistry({}) as registry:
            result = run_direct("absent", registry.url)
        self.assertEqual(result.code, EXIT_FETCH_ERROR)
        self.assertEqual(result.output, "")
        self.assertIn("не найден", result.errors)

    def test_broken_response_gives_fetch_error(self) -> None:
        """Некорректный ответ сервера дает код ошибки получения данных."""
        responses = {"broken": FakeResponse(b"not json")}
        with FakeRegistry(responses) as registry:
            result = run_direct("broken", registry.url)
        self.assertEqual(result.code, EXIT_FETCH_ERROR)
        self.assertIn("Ошибка", result.errors)

    def test_direct_mode_rejects_test_repository(self) -> None:
        """Режим direct не работает с файлом тестового репозитория."""
        path = os.path.join(DATA_DIRECTORY, "simple.txt")
        result = run_main(["-t", "-p", "A", "-r", path, "-s", "direct"])
        self.assertEqual(result.code, EXIT_CONFIG_ERROR)
        self.assertIn("только с репозиторием по URL", result.errors)


def graph_lines(file_name: str, *options: str) -> MainResult:
    """Построить граф пакета A из файла тестового репозитория."""
    path = os.path.join(DATA_DIRECTORY, file_name)
    return run_main(["-t", "-p", "A", "-r", path, *options])


class TestShowGraphTestRepository(unittest.TestCase):
    """Проверки вывода графа для тестового репозитория."""

    def test_simple_tree(self) -> None:
        """Дерево без общих зависимостей и циклов."""
        result = graph_lines("simple.txt")
        expected = [
            "Граф зависимостей пакета A: узлов 5, ребер 4",
            "A -> B, C",
            "B -> D",
            "C -> E",
            "D -> (нет зависимостей)",
            "E -> (нет зависимостей)",
            "Циклические зависимости: не обнаружены",
        ]
        self.assertEqual(result.code, EXIT_OK)
        self.assertEqual(result.output.splitlines(), expected)

    def test_diamond_lists_shared_dependency_once(self) -> None:
        """Общая зависимость присутствует в графе один раз."""
        result = graph_lines("diamond.txt")
        self.assertEqual(
            result.output.splitlines()[0],
            "Граф зависимостей пакета A: узлов 4, ребер 4",
        )
        self.assertEqual(result.output.count("D -> "), 1)

    def test_cycle_through_root_is_reported(self) -> None:
        """Цикл через корень выводится явно."""
        result = graph_lines("cycle.txt")
        self.assertEqual(result.code, EXIT_OK)
        self.assertIn("Циклические зависимости (1):", result.output)
        self.assertIn("  A -> B -> C -> A", result.output.splitlines())

    def test_inner_cycle_is_reported(self) -> None:
        """Цикл в глубине графа выводится явно."""
        result = graph_lines("inner_cycle.txt")
        self.assertIn("  B -> C -> B", result.output.splitlines())

    def test_self_loop_is_reported(self) -> None:
        """Зависимость пакета от самого себя выводится как цикл."""
        result = graph_lines("self_loop.txt")
        self.assertIn("  A -> A", result.output.splitlines())

    def test_disconnected_packages_are_ignored(self) -> None:
        """Недостижимые из корня пакеты и их цикл не выводятся."""
        result = graph_lines("disconnected.txt")
        self.assertNotIn("X", result.output)
        self.assertIn("не обнаружены", result.output)

    def test_filter_removes_package_and_its_subtree(self) -> None:
        """Фильтр исключает пакет вместе с зависимостями только через него."""
        result = graph_lines("simple.txt", "-f", "C")
        expected = [
            "Граф зависимостей пакета A: узлов 3, ребер 2",
            "A -> B",
            "B -> D",
            "D -> (нет зависимостей)",
            "Циклические зависимости: не обнаружены",
        ]
        self.assertEqual(result.output.splitlines(), expected)

    def test_filter_that_matches_nothing_changes_nothing(self) -> None:
        """Фильтр без совпадений не меняет граф."""
        plain = graph_lines("mixed.txt")
        filtered = graph_lines("mixed.txt", "-f", "Z")
        self.assertEqual(plain.output, filtered.output)

    def test_filter_that_removes_root_is_rejected(self) -> None:
        """Фильтр, исключающий корневой пакет, отклоняется."""
        result = graph_lines("simple.txt", "-f", "A")
        self.assertEqual(result.code, EXIT_CONFIG_ERROR)
        self.assertIn("содержит подстроку фильтра", result.errors)

    def test_unknown_root_package_is_reported(self) -> None:
        """Пакет, которого нет в файле, дает ошибку получения данных."""
        path = os.path.join(DATA_DIRECTORY, "simple.txt")
        result = run_main(["-t", "-p", "Z", "-r", path])
        self.assertEqual(result.code, EXIT_FETCH_ERROR)
        self.assertIn("не найден", result.errors)

    def test_malformed_file_is_reported(self) -> None:
        """Файл неверного формата дает ошибку получения данных."""
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "broken.txt")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write("A depends on B\n")
            result = run_main(["-t", "-p", "A", "-r", path])
        self.assertEqual(result.code, EXIT_FETCH_ERROR)
        self.assertIn("строка 1", result.errors)


class TestShowGraphRegistry(unittest.TestCase):
    """Проверки вывода графа для репозитория по URL."""

    def test_transitive_dependencies_are_collected(self) -> None:
        """Транзитивные зависимости загружаются по уровням."""
        responses = {
            "app": make_packument("app", "1.0.0", {"lib": "^1", "util": "2"}),
            "lib": make_packument("lib", "1.5.0", {"util": "~2.1"}),
            "util": make_packument("util", "2.1.0", {}),
        }
        with FakeRegistry(responses) as registry:
            result = run_main(["-p", "app", "-r", registry.url])
        expected = [
            "Граф зависимостей пакета app: узлов 3, ребер 3",
            "app -> lib, util",
            "lib -> util",
            "util -> (нет зависимостей)",
            "Циклические зависимости: не обнаружены",
        ]
        self.assertEqual(result.code, EXIT_OK)
        self.assertEqual(result.output.splitlines(), expected)
        self.assertEqual(len(registry.requests), 3)

    def test_cycle_between_registry_packages(self) -> None:
        """Циклические зависимости между пакетами репозитория."""
        responses = {
            "one": make_packument("one", "1.0.0", {"two": "1"}),
            "two": make_packument("two", "1.0.0", {"one": "1"}),
        }
        with FakeRegistry(responses) as registry:
            result = run_main(["-p", "one", "-r", registry.url])
        self.assertEqual(result.code, EXIT_OK)
        self.assertIn("  one -> two -> one", result.output.splitlines())

    def test_filter_skips_requests_for_excluded_packages(self) -> None:
        """Исключенные пакеты не запрашиваются из репозитория."""
        responses = {
            "app": make_packument("app", "1.0.0", {"lib": "1", "skip-me": "1"}),
            "lib": make_packument("lib", "1.0.0", {}),
        }
        with FakeRegistry(responses) as registry:
            result = run_main(["-p", "app", "-r", registry.url, "-f", "skip"])
        requested = [request.path for request in registry.requests]
        self.assertEqual(result.code, EXIT_OK)
        self.assertEqual(requested, ["app", "lib"])

    def test_alias_and_non_registry_dependencies(self) -> None:
        """Алиасы npm разворачиваются, git-зависимости пропускаются."""
        dependencies = {
            "short-name": "npm:real-name@^2.0.0",
            "from-git": "github:user/repo",
            "from-url": "https://example.org/pkg.tgz",
        }
        responses = {
            "app": make_packument("app", "1.0.0", dependencies),
            "real-name": make_packument("real-name", "2.3.0", {}),
        }
        with FakeRegistry(responses) as registry:
            result = run_main(["-p", "app", "-r", registry.url])
        self.assertEqual(result.code, EXIT_OK)
        self.assertEqual(result.output.splitlines()[1], "app -> real-name")

    def test_missing_transitive_package_is_reported(self) -> None:
        """Отсутствие транзитивной зависимости в репозитории - ошибка."""
        responses = {"app": make_packument("app", "1.0.0", {"gone": "1"})}
        with FakeRegistry(responses) as registry:
            result = run_main(["-p", "app", "-r", registry.url])
        self.assertEqual(result.code, EXIT_FETCH_ERROR)
        self.assertIn("'gone'", result.errors)


class TestFormatConfig(unittest.TestCase):
    """Проверки форматирования конфигурации."""

    def test_format_has_one_line_per_parameter(self) -> None:
        """Каждый параметр занимает отдельную строку."""
        config = parse_config(["-p", "express", "-s", "config"])
        lines = format_config(config).splitlines()
        keys = [line.split(":", 1)[0] for line in lines]
        self.assertEqual(
            keys,
            [
                "package", "repo", "test_mode", "ascii_tree", "filter",
                "show",
            ],
        )


class TestModuleLaunch(unittest.TestCase):
    """Проверка запуска через python -m depviz."""

    def run_module(self, arguments: list[str]) -> subprocess.CompletedProcess:
        """Запустить пакет отдельным процессом."""
        environment = dict(os.environ)
        environment["PYTHONPATH"] = SOURCE_DIRECTORY
        environment["PYTHONUTF8"] = "1"
        return subprocess.run(
            [sys.executable, "-m", "depviz", *arguments],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=environment,
            check=False,
        )

    def test_successful_launch(self) -> None:
        """Корректные опции дают код 0 и вывод параметров."""
        result = self.run_module(["-p", "express", "-s", "config"])
        self.assertEqual(result.returncode, EXIT_OK)
        self.assertIn("package: express", result.stdout)

    def test_failed_launch(self) -> None:
        """Некорректные опции дают код ошибки конфигурации."""
        result = self.run_module(["-p", "express", "-r", "ftp://x"])
        self.assertEqual(result.returncode, EXIT_CONFIG_ERROR)
        self.assertIn("Ошибка", result.stderr)
