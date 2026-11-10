"""Тесты интерфейса командной строки."""

import contextlib
import io
import os
import subprocess
import sys
import unittest
from typing import NamedTuple

from depviz.cli import (
    EXIT_CONFIG_ERROR,
    EXIT_OK,
    NOT_SET_LABEL,
    format_config,
    main,
)
from depviz.config import DEFAULT_REGISTRY_URL, parse_config

SOURCE_DIRECTORY = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"
)


class MainResult(NamedTuple):
    """Результат запуска main: код завершения и перехваченный вывод."""

    code: int
    output: str
    errors: str


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
        argv = ["-p", "express", "-a", "-f", "test"]
        result = run_main(argv)
        expected = [
            "package: express",
            f"repo: {DEFAULT_REGISTRY_URL}",
            "test_mode: false",
            "ascii_tree: true",
            "filter: test",
        ]
        self.assertEqual(result.code, EXIT_OK)
        self.assertEqual(result.output.splitlines(), expected)
        self.assertEqual(result.errors, "")

    def test_unset_filter_has_placeholder(self) -> None:
        """Незаданный фильтр выводится как заглушка."""
        result = run_main(["-p", "express"])
        placeholder_line = f"filter: {NOT_SET_LABEL}"
        self.assertIn(placeholder_line, result.output.splitlines())

    def test_error_goes_to_stderr(self) -> None:
        """Ошибка пишется в stderr, код завершения ненулевой."""
        result = run_main(["-p", "Bad Name"])
        self.assertEqual(result.code, EXIT_CONFIG_ERROR)
        self.assertEqual(result.output, "")
        self.assertIn("Ошибка", result.errors)


class TestFormatConfig(unittest.TestCase):
    """Проверки форматирования конфигурации."""

    def test_format_has_one_line_per_parameter(self) -> None:
        """Каждый параметр занимает отдельную строку."""
        config = parse_config(["-p", "express"])
        lines = format_config(config).splitlines()
        keys = [line.split(":", 1)[0] for line in lines]
        self.assertEqual(
            keys,
            ["package", "repo", "test_mode", "ascii_tree", "filter"],
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
        result = self.run_module(["-p", "express"])
        self.assertEqual(result.returncode, EXIT_OK)
        self.assertIn("package: express", result.stdout)

    def test_failed_launch(self) -> None:
        """Некорректные опции дают код ошибки конфигурации."""
        result = self.run_module(["-p", "express", "-r", "ftp://x"])
        self.assertEqual(result.returncode, EXIT_CONFIG_ERROR)
        self.assertIn("Ошибка", result.stderr)
