"""Тесты разбора и проверки параметров командной строки."""

import os
import tempfile
import unittest

from depviz.config import (
    DEFAULT_REGISTRY_URL,
    DEFAULT_SHOW,
    MAX_NPM_NAME_LENGTH,
    SHOW_CONFIG,
    parse_config,
)
from depviz.errors import ConfigError

REAL_PACKAGE = "express"
SCOPED_PACKAGE = "@babel/core"
CUSTOM_URL = "https://registry.example.org"
TOO_LONG_NAME = "a" * (MAX_NPM_NAME_LENGTH + 1)
GRAPH_FILE_NAME = "graph.txt"


def make_repo_file(directory: str) -> str:
    """Создать файл тестового репозитория и вернуть путь к нему."""
    path = os.path.join(directory, GRAPH_FILE_NAME)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("A: B\n")
    return path


class TestRealMode(unittest.TestCase):
    """Проверки режима работы с реальным репозиторием."""

    def test_defaults_use_public_registry(self) -> None:
        """Без опций берется реестр npm и выключенные флаги."""
        config = parse_config(["-p", REAL_PACKAGE])
        self.assertEqual(config.package, REAL_PACKAGE)
        self.assertEqual(config.repo, DEFAULT_REGISTRY_URL)
        self.assertFalse(config.test_mode)
        self.assertFalse(config.ascii_tree)
        self.assertEqual(config.filter_substring, "")
        self.assertEqual(config.show, DEFAULT_SHOW)

    def test_scoped_package_is_accepted(self) -> None:
        """Пакет с областью видимости считается корректным."""
        config = parse_config(["--package", SCOPED_PACKAGE])
        self.assertEqual(config.package, SCOPED_PACKAGE)

    def test_url_trailing_slash_is_removed(self) -> None:
        """Завершающий слеш в URL отбрасывается."""
        config = parse_config(["-p", REAL_PACKAGE, "-r", CUSTOM_URL + "/"])
        self.assertEqual(config.repo, CUSTOM_URL)

    def test_missing_package_is_rejected(self) -> None:
        """Отсутствие имени пакета приводит к ошибке."""
        with self.assertRaises(ConfigError):
            parse_config([])

    def test_invalid_package_names_are_rejected(self) -> None:
        """Имена, нарушающие правила npm, отклоняются."""
        invalid_names = [
            "", " ", "Express", "_hidden", ".dot", "a b", "a/b", "@scope",
            TOO_LONG_NAME,
        ]
        for name in invalid_names:
            with self.subTest(name=name):
                with self.assertRaises(ConfigError):
                    parse_config(["-p", name])

    def test_invalid_urls_are_rejected(self) -> None:
        """Адреса без http(s) или без хоста отклоняются."""
        invalid_urls = [
            "ftp://example.org", "registry.npmjs.org", "http://", "",
            "C:\\graph.txt",
        ]
        for url in invalid_urls:
            with self.subTest(url=url):
                with self.assertRaises(ConfigError):
                    parse_config(["-p", REAL_PACKAGE, "-r", url])


class TestTestMode(unittest.TestCase):
    """Проверки режима работы с тестовым репозиторием."""

    def test_valid_package_and_file_are_accepted(self) -> None:
        """Большие латинские буквы и существующий файл допустимы."""
        with tempfile.TemporaryDirectory() as directory:
            path = make_repo_file(directory)
            config = parse_config(["-t", "-p", "AB", "-r", path])
        self.assertTrue(config.test_mode)
        self.assertEqual(config.package, "AB")
        self.assertEqual(config.repo, path)

    def test_missing_repo_is_rejected(self) -> None:
        """Без пути к файлу тестовый режим не запускается."""
        with self.assertRaises(ConfigError):
            parse_config(["-t", "-p", "A"])

    def test_missing_file_is_rejected(self) -> None:
        """Несуществующий файл приводит к ошибке."""
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "absent.txt")
            with self.assertRaises(ConfigError):
                parse_config(["-t", "-p", "A", "-r", path])

    def test_directory_instead_of_file_is_rejected(self) -> None:
        """Путь к каталогу вместо файла приводит к ошибке."""
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ConfigError):
                parse_config(["-t", "-p", "A", "-r", directory])

    def test_non_uppercase_package_is_rejected(self) -> None:
        """Имена не из больших латинских букв отклоняются."""
        with tempfile.TemporaryDirectory() as directory:
            path = make_repo_file(directory)
            for name in ["a", "A1", "express", "A B", ""]:
                with self.subTest(name=name):
                    with self.assertRaises(ConfigError):
                        parse_config(["-t", "-p", name, "-r", path])


class TestFilterAndFlags(unittest.TestCase):
    """Проверки фильтра, флагов и неизвестных опций."""

    def test_filter_value_is_kept(self) -> None:
        """Заданная подстрока сохраняется без изменений."""
        config = parse_config(["-p", REAL_PACKAGE, "-f", "babel"])
        self.assertEqual(config.filter_substring, "babel")

    def test_invalid_filters_are_rejected(self) -> None:
        """Пустая подстрока и подстрока с пробелами отклоняются."""
        for substring in ["", " ", "a b"]:
            with self.subTest(substring=substring):
                with self.assertRaises(ConfigError):
                    parse_config(["-p", REAL_PACKAGE, "-f", substring])

    def test_ascii_tree_flag_is_enabled(self) -> None:
        """Флаг ASCII-дерева включается опцией."""
        config = parse_config(["-p", REAL_PACKAGE, "--ascii-tree"])
        self.assertTrue(config.ascii_tree)

    def test_unknown_option_is_rejected(self) -> None:
        """Неизвестная опция приводит к ошибке."""
        with self.assertRaises(ConfigError):
            parse_config(["-p", REAL_PACKAGE, "--unknown"])

    def test_option_abbreviation_is_rejected(self) -> None:
        """Сокращенное имя длинной опции не принимается."""
        with self.assertRaises(ConfigError):
            parse_config(["--pack", REAL_PACKAGE])

    def test_option_without_value_is_rejected(self) -> None:
        """Опция без значения приводит к ошибке."""
        with self.assertRaises(ConfigError):
            parse_config(["-p"])

    def test_show_value_is_kept(self) -> None:
        """Выбранное действие вывода сохраняется в конфигурации."""
        config = parse_config(["-p", REAL_PACKAGE, "--show", SHOW_CONFIG])
        self.assertEqual(config.show, SHOW_CONFIG)

    def test_unknown_show_value_is_rejected(self) -> None:
        """Неизвестное действие вывода приводит к ошибке."""
        with self.assertRaises(ConfigError):
            parse_config(["-p", REAL_PACKAGE, "--show", "everything"])
