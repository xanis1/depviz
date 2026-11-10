"""Разбор и проверка параметров командной строки."""

import argparse
import os
import re
from dataclasses import dataclass
from typing import NoReturn, Optional, Sequence
from urllib.parse import urlparse

from depviz.errors import ConfigError

PROGRAM_NAME = "depviz"
DEFAULT_REGISTRY_URL = "https://registry.npmjs.org"
ALLOWED_URL_SCHEMES = ("http", "https")
MAX_NPM_NAME_LENGTH = 214
TEST_PACKAGE_PATTERN = re.compile(r"[A-Z]+")
NPM_PACKAGE_PATTERN = re.compile(
    r"(?:@[a-z0-9\-~][a-z0-9\-._~]*/)?[a-z0-9\-~][a-z0-9\-._~]*"
)


@dataclass(frozen=True)
class Config:
    """Параметры, настраиваемые пользователем."""

    package: str
    repo: str
    test_mode: bool
    ascii_tree: bool
    filter_substring: str


class ConfigArgumentParser(argparse.ArgumentParser):
    """Парсер, который сообщает об ошибках исключением, а не выходом."""

    def error(self, message: str) -> NoReturn:
        """Передать ошибку разбора аргументов как ConfigError."""
        raise ConfigError(f"неверные аргументы командной строки: {message}")


def build_parser() -> ConfigArgumentParser:
    """Создать парсер опций командной строки."""
    parser = ConfigArgumentParser(
        prog=PROGRAM_NAME,
        description="Визуализация графа зависимостей npm-пакета.",
        allow_abbrev=False,
    )
    parser.add_argument(
        "-p", "--package", help="имя анализируемого пакета"
    )
    parser.add_argument(
        "-r",
        "--repo",
        help="URL репозитория или путь к файлу тестового репозитория",
    )
    parser.add_argument(
        "-t",
        "--test-mode",
        action="store_true",
        help="режим тестового репозитория: --repo задает путь к файлу",
    )
    parser.add_argument(
        "-a",
        "--ascii-tree",
        action="store_true",
        help="выводить зависимости в формате ASCII-дерева",
    )
    parser.add_argument(
        "-f",
        "--filter",
        dest="filter_substring",
        help="не учитывать пакеты, в имени которых есть подстрока",
    )
    return parser


def validate_test_package(package: str) -> None:
    """Проверить, что имя состоит из больших латинских букв."""
    if not TEST_PACKAGE_PATTERN.fullmatch(package):
        raise ConfigError(
            f"имя пакета '{package}' в тестовом режиме должно состоять "
            "из больших латинских букв (A-Z)"
        )


def validate_npm_package(package: str) -> None:
    """Проверить имя пакета по правилам npm."""
    too_long = len(package) > MAX_NPM_NAME_LENGTH
    if too_long or not NPM_PACKAGE_PATTERN.fullmatch(package):
        raise ConfigError(
            f"имя пакета '{package}' не соответствует правилам npm: "
            "строчные буквы, цифры, '-', '.', '_', '~', "
            "необязательный префикс '@область/'"
        )


def validate_package(package: Optional[str], test_mode: bool) -> str:
    """Проверить имя пакета в соответствии с режимом работы."""
    if package is None:
        raise ConfigError("не задано имя пакета (параметр --package)")
    if test_mode:
        validate_test_package(package)
    else:
        validate_npm_package(package)
    return package


def validate_test_repo(path: Optional[str]) -> str:
    """Проверить путь к файлу тестового репозитория."""
    if path is None or not path.strip():
        raise ConfigError(
            "в тестовом режиме необходимо задать путь к файлу "
            "репозитория (параметр --repo)"
        )
    if not os.path.exists(path):
        raise ConfigError(f"файл тестового репозитория не найден: '{path}'")
    if not os.path.isfile(path):
        raise ConfigError(f"путь '{path}' не является файлом")
    if not os.access(path, os.R_OK):
        raise ConfigError(f"нет доступа на чтение файла '{path}'")
    return path


def validate_url_repo(url: Optional[str]) -> str:
    """Проверить URL репозитория; без значения берется реестр npm."""
    if url is None:
        return DEFAULT_REGISTRY_URL
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_URL_SCHEMES or not parsed.netloc:
        raise ConfigError(
            f"некорректный URL репозитория '{url}': ожидается адрес "
            "вида http(s)://хост (для файла используйте --test-mode)"
        )
    return url.rstrip("/")


def resolve_repo(repo: Optional[str], test_mode: bool) -> str:
    """Проверить источник данных в соответствии с режимом работы."""
    if test_mode:
        return validate_test_repo(repo)
    return validate_url_repo(repo)


def validate_filter(substring: Optional[str]) -> str:
    """Проверить подстроку фильтрации; отсутствие значения допустимо."""
    if substring is None:
        return ""
    if not substring or any(char.isspace() for char in substring):
        raise ConfigError(
            "подстрока для фильтрации должна быть непустой "
            "и не содержать пробельных символов"
        )
    return substring


def parse_config(argv: Optional[Sequence[str]] = None) -> Config:
    """Разобрать аргументы командной строки и проверить параметры."""
    namespace = build_parser().parse_args(argv)
    return Config(
        package=validate_package(namespace.package, namespace.test_mode),
        repo=resolve_repo(namespace.repo, namespace.test_mode),
        test_mode=namespace.test_mode,
        ascii_tree=namespace.ascii_tree,
        filter_substring=validate_filter(namespace.filter_substring),
    )
