"""
Тесты для модуля selector.

Проверяет корректность работы классов и стратегий выбора элементов.
"""

import pytest
from typing import List
from unittest.mock import patch

from assign_bot.selector import (
    ItemSelector,
    SelectionPolicy,
    RandomStrategy,
    RoundRobinStrategy,
)


class TestSelectionStrategies:
    """Тесты для стратегий выбора."""
    
    def test_random_strategy_empty_collection(self):
        """Тест случайной стратегии с пустой коллекцией."""
        strategy = RandomStrategy[str]()
        selected, state = strategy.select([], count=3)
        
        assert selected == []
        assert state is None
    
    def test_random_strategy_normal_selection(self):
        """Тест случайной стратегии с обычным выбором."""
        strategy = RandomStrategy[str]()
        available = ["a", "b", "c", "d", "e"]
        
        selected, state = strategy.select(available, count=3)
        
        assert len(selected) == 3
        assert all(item in available for item in selected)
        assert len(set(selected)) == 3  # Без повторений
        assert state is None  # Random не использует состояние
    
    def test_random_strategy_count_exceeds_available(self):
        """Тест случайной стратегии когда запрашивается больше элементов, чем доступно."""
        strategy = RandomStrategy[str]()
        available = ["a", "b"]
        
        selected, state = strategy.select(available, count=5)
        
        assert len(selected) == 2  # Максимум доступных
        assert set(selected) == {"a", "b"}
    
    def test_round_robin_strategy_empty_collection(self):
        """Тест round-robin стратегии с пустой коллекцией."""
        strategy = RoundRobinStrategy[str]()
        selected, state = strategy.select([], count=1)
        
        assert selected == []
        assert state is None
    
    def test_round_robin_strategy_initial_state(self):
        """Тест round-robin стратегии с начальным состоянием."""
        strategy = RoundRobinStrategy[str]()
        available = ["a", "b", "c"]
        
        selected, state = strategy.select(available, count=1, state=None)
        
        assert len(selected) == 1
        assert selected[0] in available
        assert state == 0  # Индекс первого элемента
    
    def test_round_robin_strategy_sequential_selections(self):
        """Тест последовательных выборов round-robin."""
        strategy = RoundRobinStrategy[str]()
        available = ["a", "b", "c"]
        
        state = None
        selections = []
        
        for _ in range(6):  # 2 полных цикла
            selected, state = strategy.select(available, count=1, state=state)
            selections.extend(selected)
        
        # Проверяем цикличность
        assert selections == ["a", "b", "c", "a", "b", "c"]
    
    def test_round_robin_strategy_multiple_count(self):
        """Тест round-robin с запросом нескольких элементов (должен возвращать только 1)."""
        strategy = RoundRobinStrategy[str]()
        available = ["a", "b", "c"]
        
        selected, state = strategy.select(available, count=3, state=None)
        
        assert len(selected) == 1  # Round-robin всегда возвращает 1 элемент


class TestItemSelector:
    """Тесты для класса ItemSelector."""
    
    @pytest.fixture
    def sample_users(self) -> List[str]:
        """Фикстура с примером пользователей."""
        return ["@alice", "@bob", "@charlie", "@david", "@eve"]
    
    def test_selector_initialization(self):
        """Тест инициализации селектора."""
        selector = ItemSelector[str]()
        
        assert selector.collection == []
        assert selector.policy == SelectionPolicy.RANDOM
        assert selector.state is None
    
    def test_selector_set_collection(self, sample_users):
        """Тест установки коллекции."""
        selector = ItemSelector[str]()
        selector.set_collection(sample_users)
        
        assert selector.collection == sample_users
        assert selector.state is None  # Состояние сбрасывается
    
    def test_selector_set_policy(self):
        """Тест изменения политики."""
        selector = ItemSelector[str]()
        original_state = "some_state"
        selector.state = original_state
        
        selector.set_policy(SelectionPolicy.ROUND_ROBIN)
        
        assert selector.policy == SelectionPolicy.ROUND_ROBIN
        assert selector.state is None  # Состояние сбрасывается при смене политики
    
    def test_selector_set_same_policy(self):
        """Тест установки той же политики (не должно сбрасывать состояние)."""
        selector = ItemSelector[str]()
        selector.policy = SelectionPolicy.RANDOM
        original_state = "some_state"
        selector.state = original_state
        
        selector.set_policy(SelectionPolicy.RANDOM)
        
        assert selector.policy == SelectionPolicy.RANDOM
        assert selector.state == original_state  # Состояние НЕ сбрасывается
    
    def test_selector_random_selection(self, sample_users):
        """Тест случайного выбора через селектор."""
        selector = ItemSelector[str]()
        selector.set_collection(sample_users)
        selector.set_policy(SelectionPolicy.RANDOM)
        
        selected = selector.select(count=3)
        
        assert len(selected) == 3
        assert all(user in sample_users for user in selected)
        assert len(set(selected)) == 3  # Без повторений
    
    def test_selector_round_robin_selection(self, sample_users):
        """Тест round-robin выбора через селектор."""
        selector = ItemSelector[str]()
        selector.set_collection(sample_users)
        selector.set_policy(SelectionPolicy.ROUND_ROBIN)
        
        selections = []
        for _ in range(len(sample_users) * 2):  # 2 полных цикла
            selected = selector.select(count=1)
            selections.extend(selected)
        
        # Проверяем цикличность
        expected = sample_users * 2
        assert selections == expected
    
    def test_selector_select_from_available_valid(self, sample_users):
        """Тест выбора из подмножества доступных."""
        selector = ItemSelector[str]()
        selector.set_collection(sample_users)
        
        available = ["@alice", "@charlie", "@eve"]
        selected = selector.select_from_available(available, count=2)
        
        assert len(selected) <= 2
        assert all(user in available for user in selected)
    
    def test_selector_select_from_available_invalid(self, sample_users):
        """Тест выбора из подмножества с элементами не из коллекции."""
        selector = ItemSelector[str]()
        selector.set_collection(sample_users)
        
        available = ["@alice", "@unknown_user"]  # unknown_user не в коллекции
        
        with pytest.raises(ValueError, match="не найден в коллекции"):
            selector.select_from_available(available, count=1)
    
    def test_selector_select_from_empty_available(self, sample_users):
        """Тест выбора из пустого подмножества."""
        selector = ItemSelector[str]()
        selector.set_collection(sample_users)
        
        selected = selector.select_from_available([], count=3)
        
        assert selected == []
    
    def test_selector_select_empty_collection(self):
        """Тест выбора из пустой коллекции."""
        selector = ItemSelector[str]()
        
        selected = selector.select(count=5)
        
        assert selected == []
    
    def test_selector_reset_state(self, sample_users):
        """Тест сброса состояния."""
        selector = ItemSelector[str]()
        selector.set_collection(sample_users)
        selector.set_policy(SelectionPolicy.ROUND_ROBIN)
        
        # Делаем выбор, чтобы установить состояние
        selector.select(count=1)
        assert selector.state is not None
        
        # Сбрасываем состояние
        selector.reset_state()
        assert selector.state is None
    
    def test_selector_get_info(self, sample_users):
        """Тест получения информации о селекторе."""
        selector = ItemSelector[str]()
        selector.set_collection(sample_users)
        selector.set_policy(SelectionPolicy.ROUND_ROBIN)
        
        info = selector.get_info()
        
        assert info["collection_size"] == len(sample_users)
        assert info["policy"] == SelectionPolicy.ROUND_ROBIN.value
        assert "state" in info
    
    def test_selector_unsupported_policy(self):
        """Тест неподдерживаемой политики."""
        selector = ItemSelector[str]()
        
        # Напрямую устанавливаем недопустимую политику
        selector.policy = "invalid_policy"  # type: ignore
        
        with pytest.raises(ValueError, match="Неподдерживаемая политика"):
            selector._create_strategy()


class TestIntegrationScenarios:
    """Интеграционные тесты реальных сценариев использования."""
    
    def test_telegram_bot_scenario(self):
        """Тест сценария использования в Telegram боте."""
        # Инициализация как в боте
        all_participants = ["@alice", "@bob", "@charlie", "@david", "@eve"]
        selector = ItemSelector[str]()
        selector.set_collection(all_participants)
        
        # Сценарий 1: Round-robin назначение
        selector.set_policy(SelectionPolicy.ROUND_ROBIN)
        active_today = ["@alice", "@charlie", "@eve"]  # Не все активны
        
        assigned1 = selector.select_from_available(active_today, count=1)
        assigned2 = selector.select_from_available(active_today, count=1)
        assigned3 = selector.select_from_available(active_today, count=1)
        assigned4 = selector.select_from_available(active_today, count=1)
        
        # Проверяем цикличность в рамках активных
        all_assigned = [assigned1[0], assigned2[0], assigned3[0], assigned4[0]]
        assert len(set(all_assigned)) <= len(active_today)
        
        # Сценарий 2: Random назначение
        selector.set_policy(SelectionPolicy.RANDOM)
        
        assigned_random = selector.select_from_available(active_today, count=2)
        assert len(assigned_random) == 2
        assert all(user in active_today for user in assigned_random)
    
    def test_state_persistence_across_selections(self):
        """Тест сохранения состояния между выборами."""
        users = ["@user1", "@user2", "@user3"]
        selector = ItemSelector[str]()
        selector.set_collection(users)
        selector.set_policy(SelectionPolicy.ROUND_ROBIN)
        
        # Делаем несколько выборов
        results = []
        for _ in range(6):
            selected = selector.select(count=1)
            results.extend(selected)
        
        # Проверяем, что состояние корректно сохранялось
        expected = users * 2  # 2 полных цикла
        assert results == expected
    
    @patch('assign_bot.selector.random.sample')
    def test_random_selection_deterministic(self, mock_sample):
        """Тест детерминированного поведения random выбора (для предсказуемых тестов)."""
        mock_sample.return_value = ["@bob", "@alice"]
        
        selector = ItemSelector[str]()
        selector.set_collection(["@alice", "@bob", "@charlie"])
        selector.set_policy(SelectionPolicy.RANDOM)
        
        selected = selector.select(count=2)
        
        assert selected == ["@bob", "@alice"]
        mock_sample.assert_called_once_with(["@alice", "@bob", "@charlie"], k=2)


@pytest.mark.parametrize("policy,expected_count", [
    (SelectionPolicy.RANDOM, 2),
    (SelectionPolicy.ROUND_ROBIN, 1),
])
def test_policy_specific_behavior(policy, expected_count):
    """Параметризованный тест поведения разных политик."""
    users = ["@user1", "@user2", "@user3", "@user4"]
    selector = ItemSelector[str]()
    selector.set_collection(users)
    selector.set_policy(policy)
    
    if policy == SelectionPolicy.RANDOM:
        # Для random запрашиваем 2, ожидаем 2
        selected = selector.select(count=2)
        assert len(selected) == expected_count
    else:
        # Для round-robin запрашиваем 3, ожидаем 1
        selected = selector.select(count=3)
        assert len(selected) == expected_count
