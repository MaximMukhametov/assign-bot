"""
Модуль для выбора элементов из коллекции с различными стратегиями.

Предоставляет универсальный класс ItemSelector для выбора N элементов
из заранее установленной коллекции с поддержкой различных политик выбора.
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Generic, List, Optional, Sequence, TypeVar

T = TypeVar('T')


class SelectionPolicy(str, Enum):
    """Политики выбора элементов из коллекции."""
    ROUND_ROBIN = "round_robin"
    RANDOM = "random"


class SelectionStrategy(ABC, Generic[T]):
    """Абстрактная стратегия выбора элементов."""
    
    @abstractmethod
    def select(self, available: Sequence[T], count: int, state: Any = None) -> tuple[List[T], Any]:
        """
        Выбирает элементы из доступных.
        
        Args:
            available: Доступные для выбора элементы
            count: Количество элементов для выбора
            state: Текущее состояние стратегии (для round-robin и т.д.)
            
        Returns:
            Tuple из выбранных элементов и нового состояния
        """
        pass


class RandomStrategy(SelectionStrategy[T]):
    """Стратегия случайного выбора."""
    
    def select(self, available: Sequence[T], count: int, state: Any = None) -> tuple[List[T], Any]:
        """Выбирает случайные элементы без повторений."""
        if not available:
            return [], state
        
        actual_count = min(count, len(available))
        selected = random.sample(list(available), k=actual_count)
        return selected, state


class RoundRobinStrategy(SelectionStrategy[T]):
    """Стратегия round-robin выбора."""
    
    def select(self, available: Sequence[T], count: int, state: Any = None) -> tuple[List[T], Any]:
        """
        Выбирает элементы по round-robin.
        
        State представляет собой индекс последнего выбранного элемента
        в полной коллекции (не в available).
        """
        if not available:
            return [], state
            
        if state is None:
            state = -1
            
        # Находим следующий доступный элемент, начиная с состояния
        selected = []
        current_state = state
        
        # Для round-robin берём только 1 элемент (следующий в очереди)
        actual_count = min(count, 1)
        
        for _ in range(actual_count):
            if not available:
                break
                
            # Находим индекс следующего доступного элемента
            found = False
            for i in range(len(available)):
                # Простая логика: берём следующий после последнего выбранного
                candidate_idx = (current_state + 1 + i) % len(available)
                if candidate_idx < len(available):
                    selected.append(available[candidate_idx])
                    current_state = candidate_idx
                    found = True
                    break
                    
            if not found and available:
                # Если не нашли, берём первый доступный
                selected.append(available[0])
                current_state = 0
                
        return selected, current_state


@dataclass
class ItemSelector(Generic[T]):
    """
    Универсальный селектор элементов с поддержкой различных стратегий.
    
    Attributes:
        collection: Полная коллекция элементов
        policy: Политика выбора
        state: Внутреннее состояние селектора (для round-robin и т.д.)
    """
    
    collection: List[T] = field(default_factory=list)
    policy: SelectionPolicy = SelectionPolicy.RANDOM
    state: Any = field(default=None)
    
    def __post_init__(self) -> None:
        """Инициализация стратегии на основе политики."""
        self._strategy = self._create_strategy()
    
    def _create_strategy(self) -> SelectionStrategy[T]:
        """Создаёт стратегию на основе текущей политики."""
        if self.policy == SelectionPolicy.RANDOM:
            return RandomStrategy()
        elif self.policy == SelectionPolicy.ROUND_ROBIN:
            return RoundRobinStrategy()
        else:
            raise ValueError(f"Неподдерживаемая политика: {self.policy}")
    
    def set_collection(self, items: Sequence[T]) -> None:
        """Устанавливает коллекцию элементов."""
        self.collection = list(items)
        # При изменении коллекции сбрасываем состояние
        self.state = None
    
    def set_policy(self, policy: SelectionPolicy) -> None:
        """Изменяет политику выбора."""
        if self.policy != policy:
            self.policy = policy
            self._strategy = self._create_strategy()
            # При изменении политики сбрасываем состояние
            self.state = None
    
    def select_from_available(self, available: Sequence[T], count: int = 1) -> List[T]:
        """
        Выбирает элементы из подмножества доступных.
        
        Args:
            available: Подмножество элементов для выбора (должны быть из collection)
            count: Количество элементов для выбора
            
        Returns:
            Список выбранных элементов
            
        Raises:
            ValueError: Если available содержит элементы не из collection
        """
        if not available:
            return []
            
        # Проверяем, что все available элементы есть в коллекции
        collection_set = set(self.collection)
        for item in available:
            if item not in collection_set:
                raise ValueError(f"Элемент {item} не найден в коллекции")
        
        selected, new_state = self._strategy.select(available, count, self.state)
        self.state = new_state
        return selected
    
    def select(self, count: int = 1) -> List[T]:
        """
        Выбирает элементы из всей коллекции.
        
        Args:
            count: Количество элементов для выбора
            
        Returns:
            Список выбранных элементов
        """
        return self.select_from_available(self.collection, count)
    
    def reset_state(self) -> None:
        """Сбрасывает внутреннее состояние селектора."""
        self.state = None
        
    def get_info(self) -> dict[str, Any]:
        """Возвращает информацию о текущем состоянии селектора."""
        return {
            "collection_size": len(self.collection),
            "policy": self.policy.value,
            "state": self.state,
        }
