"""
Конфигурация pytest.

Настройка путей импорта и общие фикстуры для тестов.
"""

import sys
from pathlib import Path

# Добавляем src в sys.path для корректных импортов
project_root = Path(__file__).parent.parent
src_path = project_root / "src"

if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

import pytest


@pytest.fixture(autouse=True)
def clean_state():
    """
    Автоматическая очистка состояния между тестами.
    
    Очищает глобальное состояние бота для изоляции тестов.
    """
    # Очищаем состояние перед тестом
    yield
    
    # Очищаем состояние после теста
    try:
        from assign_bot.bot import CHAT_STATE, PENDING, EXPECT_CONFIG
        CHAT_STATE.clear()
        PENDING.clear()
        EXPECT_CONFIG.clear()
    except ImportError:
        # Если модули не загружены, игнорируем
        pass
