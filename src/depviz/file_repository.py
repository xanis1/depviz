"""Тестовый репозиторий: граф зависимостей, описанный в текстовом файле."""

import re

from depviz.config import TEST_PACKAGE_PATTERN
from depviz.errors import FetchError, MetadataFormatError
from depviz.errors import PackageNotFoundError

FILE_ENCODING = "utf-8-sig"
FIRST_LINE_NUMBER = 1
LINE_PATTERN = re.compile(r"\s*(?P<name>[^:\s]+)\s*:(?P<rest>.*)")
SEPARATOR_PATTERN = re.compile(r"[\s,]+")


class FileRepository:
    """Репозиторий пакетов, загруженный из файла описания графа."""

    def __init__(self, packages: dict[str, list[str]], origin: str) -> None:
        """Сохранить описание пакетов и путь к файлу-источнику."""
        self.packages = packages
        self.origin = origin

    def get_dependencies(self, package: str) -> list[str]:
        """Вернуть прямые зависимости пакета из описания графа."""
        if package not in self.packages:
            raise PackageNotFoundError(package, self.origin)
        return list(self.packages[package])


def validate_package_name(name: str, line_number: int) -> None:
    """Проверить, что имя пакета состоит из больших латинских букв."""
    if not TEST_PACKAGE_PATTERN.fullmatch(name):
        raise MetadataFormatError(
            f"строка {line_number}: имя пакета '{name}' должно состоять "
            "из больших латинских букв (A-Z)"
        )


def parse_dependency_names(text: str, line_number: int) -> list[str]:
    """Разобрать перечень зависимостей, разделенных пробелами или запятыми."""
    names = [item for item in SEPARATOR_PATTERN.split(text.strip()) if item]
    for name in names:
        validate_package_name(name, line_number)
    return list(dict.fromkeys(names))


def parse_line(line: str, line_number: int) -> tuple[str, list[str]]:
    """Разобрать строку вида 'A: B C' в имя пакета и его зависимости."""
    match = LINE_PATTERN.fullmatch(line)
    if match is None:
        raise MetadataFormatError(
            f"строка {line_number}: ожидался формат 'ПАКЕТ: ЗАВИСИМОСТИ'"
        )
    name = match.group("name")
    validate_package_name(name, line_number)
    return name, parse_dependency_names(match.group("rest"), line_number)


def add_mentioned_packages(
    packages: dict[str, list[str]]
) -> dict[str, list[str]]:
    """Добавить пакеты, упомянутые только как зависимости, без связей."""
    for dependencies in list(packages.values()):
        for name in dependencies:
            packages.setdefault(name, [])
    return packages


def parse_repository(text: str) -> dict[str, list[str]]:
    """Разобрать текст описания графа в словарь пакетов."""
    packages: dict[str, list[str]] = {}
    lines = enumerate(text.splitlines(), start=FIRST_LINE_NUMBER)
    for line_number, line in lines:
        if not line.strip():
            continue
        name, dependencies = parse_line(line, line_number)
        if name in packages:
            raise MetadataFormatError(
                f"строка {line_number}: пакет '{name}' описан повторно"
            )
        packages[name] = dependencies
    return add_mentioned_packages(packages)


def read_text(path: str) -> str:
    """Прочитать файл описания графа целиком."""
    try:
        with open(path, encoding=FILE_ENCODING) as handle:
            return handle.read()
    except (OSError, UnicodeDecodeError) as error:
        raise FetchError(
            f"не удалось прочитать файл '{path}': {error}"
        ) from error


def load_file_repository(path: str) -> FileRepository:
    """Загрузить тестовый репозиторий из файла описания графа."""
    text = read_text(path)
    try:
        packages = parse_repository(text)
    except MetadataFormatError as error:
        raise MetadataFormatError(f"файл '{path}', {error}") from error
    return FileRepository(packages, path)
