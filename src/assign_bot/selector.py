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
    def select(self, available: Sequence[T], count: int, **kwargs) -> List[T]:
        """
        Выбирает элементы из доступных.
        
        Args:
            available: Доступные для выбора элементы
            count: Количество элементов для выбора
            **kwargs: Дополнительные параметры для стратегии
        
        Returns:
            Список выбранных элементов
        """
        pass
    
    @abstractmethod 
    def reset(self) -> None:
        """Сбрасывает внутреннее состояние стратегии."""
        pass


class RandomStrategy(SelectionStrategy[T]):
    """Стратегия случайного выбора."""
    
    def select(self, available: Sequence[T], count: int, **kwargs) -> List[T]:
        """Выбирает случайные элементы без повторений."""
        if not available:
            return []
        
        actual_count = min(count, len(available))
        selected = random.sample(list(available), k=actual_count)
        return selected
    
    def reset(self) -> None:
        """Сбрасывает состояние. У RandomStrategy нет состояния."""
        pass


class RoundRobinStrategy(SelectionStrategy[T]):
    """Стратегия round-robin выбора с внутренним состоянием."""
    
    def __init__(self) -> None:
        """Инициализация стратегии с внутренним состоянием."""
        self._state: Optional[int] = None
    
    def select(self, available: Sequence[T], count: int, **kwargs) -> List[T]:
        """
        Выбирает элементы по round-robin с учётом полной коллекции.
        
        Args:
            available: Доступные для выбора элементы (подмножество full_collection)
            count: Количество элементов для выбора
            **kwargs: Должен содержать 'full_collection' - полную коллекцию элементов
        
        Returns:
            Список выбранных элементов
            
        Raises:
            ValueError: Если full_collection не передана
        """
        if not available:
            return []
            
        if self._state is None:
            self._state = -1
            
        full_collection = kwargs.get('full_collection')
        if full_collection is None:
            raise ValueError("full_collection обязательна для RoundRobinStrategy")
            
        selected = []
        actual_count = min(count, len(available))
        available_set = set(available)
        
        # Ищем следующие доступные элементы в полной коллекции
        attempts = 0
        max_attempts = len(full_collection) * 2  # Защита от бесконечного цикла
        
        while len(selected) < actual_count and attempts < max_attempts:
            attempts += 1
            self._state = (self._state + 1) % len(full_collection)
            candidate = full_collection[self._state]
            
            if candidate in available_set:
                selected.append(candidate)
                
        return selected
    
    def reset(self) -> None:
        """Сбрасывает внутреннее состояние round-robin."""
        self._state = None


class StrategyMapper:
    """Маппер для создания стратегий выбора по политике."""
    
    @staticmethod
    def create_strategy(policy: SelectionPolicy) -> SelectionStrategy[Any]:
        """
        Создаёт стратегию выбора по заданной политике.
        
        Args:
            policy: Политика выбора
            
        Returns:
            Экземпляр соответствующей стратегии
            
        Raises:
            ValueError: Если политика не поддерживается
        """
        strategy_map = {
            SelectionPolicy.RANDOM: RandomStrategy,
            SelectionPolicy.ROUND_ROBIN: RoundRobinStrategy,
        }
        
        strategy_class = strategy_map.get(policy)
        if strategy_class is None:
            raise ValueError(f"Неподдерживаемая политика: {policy}")
        
        return strategy_class()
    
    @staticmethod
    def get_strategy_kwargs(policy: SelectionPolicy, full_collection: Sequence = None) -> dict:
        """
        Возвращает дополнительные параметры для стратегии.
        
        Args:
            policy: Политика выбора
            full_collection: Полная коллекция (для round-robin)
            
        Returns:
            Словарь с параметрами для передачи в strategy.select()
        """
        if policy == SelectionPolicy.ROUND_ROBIN:
            return {'full_collection': full_collection}
        return {}


@dataclass
class ItemSelector(Generic[T]):
    """
    Универсальный селектор элементов с поддержкой различных стратегий.
    
    Attributes:
        collection: Полная коллекция элементов
        policy: Политика выбора
    """
    
    collection: List[T] = field(default_factory=list)
    policy: SelectionPolicy = SelectionPolicy.RANDOM
    
    def __post_init__(self) -> None:
        """Инициализация стратегии на основе политики."""
        self._strategy = self._create_strategy()
    
    def _create_strategy(self) -> SelectionStrategy[T]:
        """Создаёт стратегию на основе текущей политики."""
        return StrategyMapper.create_strategy(self.policy)
    
    def set_collection(self, items: Sequence[T]) -> None:
        """Устанавливает коллекцию элементов."""
        self.collection = list(items)
        # При изменении коллекции сбрасываем состояние стратегии
        self._strategy.reset()
    
    def set_policy(self, policy: SelectionPolicy) -> None:
        """Изменяет политику выбора."""
        if self.policy != policy:
            self.policy = policy
            self._strategy = self._create_strategy()
            # При изменении политики новая стратегия создается с чистым состоянием
    
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
        
        # Получаем дополнительные параметры для стратегии
        strategy_kwargs = StrategyMapper.get_strategy_kwargs(self.policy, full_collection=self.collection)
        
        # Выполняем выбор - стратегия сама управляет состоянием
        selected = self._strategy.select(available, count, **strategy_kwargs)
        
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
        """Сбрасывает внутреннее состояние стратегии."""
        self._strategy.reset()
        
    def get_info(self) -> dict[str, Any]:
        """Возвращает информацию о текущем состоянии селектора."""
        return {
            "collection_size": len(self.collection),
            "policy": self.policy.value,
        }
