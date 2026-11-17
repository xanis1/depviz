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


def run_graph(package: str, repo_url: str, *options: str) -> MainResult:
    """Вывести список связей графа пакета из репозитория по URL."""
    return run_main(["-p", package, "-r", repo_url, "-s", "graph", *options])


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
    return run_main(["-t", "-p", "A", "-r", path, "-s", "graph", *options])


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


def reverse_lines(
    file_name: str, package: str, *options: str
) -> MainResult:
    """Найти обратные зависимости пакета в файле тестового репозитория."""
    path = os.path.join(DATA_DIRECTORY, file_name)
    argv = ["-t", "-p", package, "-r", path, "-s", "reverse", *options]
    return run_main(argv)


class TestShowReverse(unittest.TestCase):
    """Проверки вывода обратных зависимостей."""

    def test_chain_of_dependents(self) -> None:
        """Зависимые пакеты выводятся по уровням."""
        result = reverse_lines("simple.txt", "D")
        expected = [
            "Обратные зависимости пакета D (всего 2):",
            "  уровень 1: B",
            "  уровень 2: A",
            "Циклические зависимости: не обнаружены",
        ]
        self.assertEqual(result.code, EXIT_OK)
        self.assertEqual(result.output.splitlines(), expected)

    def test_shared_dependency_has_several_direct_dependents(self) -> None:
        """У общей зависимости несколько прямых зависимых пакетов."""
        result = reverse_lines("diamond.txt", "D")
        lines = result.output.splitlines()
        self.assertEqual(lines[0], "Обратные зависимости пакета D (всего 3):")
        self.assertEqual(lines[1], "  уровень 1: B, C")
        self.assertEqual(lines[2], "  уровень 2: A")

    def test_root_package_has_no_dependents(self) -> None:
        """У корневого пакета обратных зависимостей нет."""
        result = reverse_lines("simple.txt", "A")
        self.assertEqual(
            result.output.splitlines()[0],
            "Обратные зависимости пакета A: отсутствуют",
        )

    def test_deep_graph_levels(self) -> None:
        """В смешанном графе зависимые пакеты делятся на пять уровней."""
        result = reverse_lines("mixed.txt", "K")
        expected_levels = [
            "  уровень 1: J",
            "  уровень 2: F, G",
            "  уровень 3: B, C, D",
            "  уровень 4: A",
            "  уровень 5: H",
        ]
        self.assertEqual(result.output.splitlines()[1:6], expected_levels)

    def test_cycle_is_reported_in_reverse_direction(self) -> None:
        """Цикл выводится в направлении 'зависит от'."""
        result = reverse_lines("cycle.txt", "A")
        self.assertIn("  A <- C <- B <- A", result.output.splitlines())

    def test_cycle_that_does_not_include_target(self) -> None:
        """Цикл вдали от целевого пакета также обнаруживается."""
        result = reverse_lines("mixed.txt", "K")
        self.assertIn("  A <- H <- D <- A", result.output.splitlines())

    def test_self_dependency_is_not_listed_as_dependent(self) -> None:
        """Сам пакет не входит в свой список, но цикл показан."""
        result = reverse_lines("self_loop.txt", "A")
        self.assertIn("отсутствуют", result.output)
        self.assertIn("  A <- A", result.output.splitlines())

    def test_cycle_between_unreachable_packages(self) -> None:
        """Зависимость внутри цикла находится независимо от корня A."""
        result = reverse_lines("disconnected.txt", "Y")
        self.assertIn("  уровень 1: X", result.output.splitlines())
        self.assertIn("  Y <- X <- Y", result.output.splitlines())

    def test_filter_excludes_dependent_package(self) -> None:
        """Исключенный фильтром пакет не попадает в список зависимых."""
        result = reverse_lines("diamond.txt", "D", "-f", "B")
        lines = result.output.splitlines()
        self.assertEqual(lines[0], "Обратные зависимости пакета D (всего 2):")
        self.assertEqual(lines[1], "  уровень 1: C")

    def test_filter_that_removes_target_is_rejected(self) -> None:
        """Фильтр, исключающий сам пакет, отклоняется."""
        result = reverse_lines("diamond.txt", "D", "-f", "D")
        self.assertEqual(result.code, EXIT_CONFIG_ERROR)

    def test_unknown_package_is_reported(self) -> None:
        """Пакет, которого нет в файле, дает ошибку получения данных."""
        result = reverse_lines("simple.txt", "Z")
        self.assertEqual(result.code, EXIT_FETCH_ERROR)
        self.assertIn("не найден", result.errors)

    def test_registry_mode_is_not_supported(self) -> None:
        """Для репозитория по URL режим reverse недоступен."""
        result = run_main(["-p", "express", "-s", "reverse"])
        self.assertEqual(result.code, EXIT_CONFIG_ERROR)
        self.assertIn("только с тестовым репозиторием", result.errors)


class TestShowD2(unittest.TestCase):
    """Проверки вывода описания графа на языке D2."""

    def test_d2_is_printed_by_default(self) -> None:
        """Без опции --show выводится описание графа на D2."""
        path = os.path.join(DATA_DIRECTORY, "diamond.txt")
        result = run_main(["-t", "-p", "A", "-r", path])
        expected = ['"A" -> "B"', '"A" -> "C"', '"B" -> "D"', '"C" -> "D"']
        self.assertEqual(result.code, EXIT_OK)
        self.assertEqual(result.output.splitlines(), expected)

    def test_d2_follows_breadth_first_order(self) -> None:
        """Связи в описании идут в порядке обхода графа в ширину."""
        path = os.path.join(DATA_DIRECTORY, "mixed.txt")
        lines = run_main(["-t", "-p", "A", "-r", path]).output.splitlines()
        self.assertEqual(lines[:3], ['"A" -> "B"', '"A" -> "C"', '"A" -> "D"'])
        self.assertEqual(len(lines), 15)

    def test_cycle_is_described_in_d2(self) -> None:
        """Циклическая зависимость присутствует в описании D2."""
        path = os.path.join(DATA_DIRECTORY, "cycle.txt")
        result = run_main(["-t", "-p", "A", "-r", path])
        self.assertIn('"C" -> "A"', result.output.splitlines())

    def test_filter_is_applied_to_d2(self) -> None:
        """Исключенные фильтром пакеты не попадают в описание D2."""
        path = os.path.join(DATA_DIRECTORY, "simple.txt")
        result = run_main(["-t", "-p", "A", "-r", path, "-f", "C"])
        self.assertEqual(
            result.output.splitlines(), ['"A" -> "B"', '"B" -> "D"']
        )

    def test_single_package_d2(self) -> None:
        """Для пакета без зависимостей выводится одна строка."""
        responses = {"leaf": make_packument("leaf", "1.0.0", {})}
        with FakeRegistry(responses) as registry:
            result = run_main(["-p", "leaf", "-r", registry.url])
        self.assertEqual(result.output.splitlines(), ['"leaf"'])

    def test_scoped_packages_are_quoted(self) -> None:
        """Имена с @, / и точками оформляются корректно."""
        responses = {
            "@scope/lib": make_packument(
                "@scope/lib", "1.0.0", {"lodash.merge": "1", "left-pad": "1"}
            ),
            "lodash.merge": make_packument("lodash.merge", "1.0.0", {}),
            "left-pad": make_packument("left-pad", "1.0.0", {}),
        }
        with FakeRegistry(responses) as registry:
            result = run_main(["-p", "@scope/lib", "-r", registry.url])
        expected = [
            '"@scope/lib" -> "left-pad"',
            '"@scope/lib" -> "lodash.merge"',
        ]
        self.assertEqual(result.output.splitlines(), expected)


class TestShowAsciiTree(unittest.TestCase):
    """Проверки вывода ASCII-дерева по параметру --ascii-tree."""

    def test_tree_follows_d2_when_flag_is_set(self) -> None:
        """С флагом -a после D2 выводится дерево зависимостей."""
        path = os.path.join(DATA_DIRECTORY, "diamond.txt")
        result = run_main(["-t", "-p", "A", "-r", path, "-a"])
        expected = [
            '"A" -> "B"',
            '"A" -> "C"',
            '"B" -> "D"',
            '"C" -> "D"',
            "",
            "A",
            "|-- B",
            "|   `-- D",
            "`-- C",
            "    `-- D",
        ]
        self.assertEqual(result.code, EXIT_OK)
        self.assertEqual(result.output.splitlines(), expected)

    def test_tree_is_absent_without_flag(self) -> None:
        """Без флага дерево не выводится."""
        path = os.path.join(DATA_DIRECTORY, "diamond.txt")
        result = run_main(["-t", "-p", "A", "-r", path])
        self.assertNotIn("|--", result.output)

    def test_tree_follows_graph_listing(self) -> None:
        """Режим graph тоже поддерживает вывод дерева."""
        path = os.path.join(DATA_DIRECTORY, "simple.txt")
        result = run_main(["-t", "-p", "A", "-r", path, "-s", "graph", "-a"])
        lines = result.output.splitlines()
        self.assertIn("A -> B, C", lines)
        self.assertIn("|-- B", lines)

    def test_cycle_marks_in_tree(self) -> None:
        """Цикл в дереве помечается."""
        path = os.path.join(DATA_DIRECTORY, "cycle.txt")
        result = run_main(["-t", "-p", "A", "-r", path, "-a"])
        self.assertIn("        `-- A (цикл)", result.output.splitlines())

    def test_flag_does_not_change_config_output(self) -> None:
        """Режим config выводит только параметры."""
        result = run_main(["-p", "express", "-a", "-s", "config"])
        self.assertIn("ascii_tree: true", result.output.splitlines())
        self.assertNotIn("|--", result.output)

    def test_tree_for_registry_packages(self) -> None:
        """Дерево строится и для репозитория по URL."""
        responses = {
            "app": make_packument("app", "1.0.0", {"lib": "1"}),
            "lib": make_packument("lib", "1.0.0", {}),
        }
        with FakeRegistry(responses) as registry:
            result = run_main(["-p", "app", "-r", registry.url, "-a"])
        self.assertEqual(
            result.output.splitlines()[-2:], ["app", "`-- lib"]
        )


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
            result = run_graph("app", registry.url)
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
            result = run_graph("one", registry.url)
        self.assertEqual(result.code, EXIT_OK)
        self.assertIn("  one -> two -> one", result.output.splitlines())

    def test_filter_skips_requests_for_excluded_packages(self) -> None:
        """Исключенные пакеты не запрашиваются из репозитория."""
        responses = {
            "app": make_packument("app", "1.0.0", {"lib": "1", "skip-me": "1"}),
            "lib": make_packument("lib", "1.0.0", {}),
        }
        with FakeRegistry(responses) as registry:
            result = run_graph("app", registry.url, "-f", "skip")
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
            result = run_graph("app", registry.url)
        self.assertEqual(result.code, EXIT_OK)
        self.assertEqual(result.output.splitlines()[1], "app -> real-name")

    def test_missing_transitive_package_is_reported(self) -> None:
        """Отсутствие транзитивной зависимости в репозитории - ошибка."""
        responses = {"app": make_packument("app", "1.0.0", {"gone": "1"})}
        with FakeRegistry(responses) as registry:
            result = run_graph("app", registry.url)
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
