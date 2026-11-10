"""Модульные тесты инструмента визуализации графа зависимостей."""

import os
import sys

SOURCE_DIRECTORY = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"
)

if SOURCE_DIRECTORY not in sys.path:
    sys.path.insert(0, SOURCE_DIRECTORY)
