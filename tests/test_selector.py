"""
Tests for selector module.

Verifies correct operation of classes and strategies for element selection.
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


class TestRandomStrategy:
    """Tests for random selection strategy."""

    def test_empty_collection(self):
        """Test random strategy with empty collection."""
        strategy = RandomStrategy[str]()
        selected = strategy.select([], count=3)

        assert selected == []

    def test_normal_selection(self):
        """Test random strategy with normal selection."""
        strategy = RandomStrategy[str]()
        available = ["a", "b", "c", "d", "e"]

        selected = strategy.select(available, count=3)

        assert len(selected) == 3
        assert all(item in available for item in selected)
        assert len(set(selected)) == 3  # Without repetitions

    def test_count_exceeds_available(self):
        """Test random strategy when more elements requested than available."""
        strategy = RandomStrategy[str]()
        available = ["a", "b"]

        selected = strategy.select(available, count=5)

        assert len(selected) == 2  # Maximum available
        assert set(selected) == {"a", "b"}

    def test_state_independence(self):
        """Test that random strategy doesn't depend on state and reset doesn't break anything."""
        strategy = RandomStrategy[str]()
        available = ["a", "b", "c"]

        # Выполняем несколько выборов
        selected1 = strategy.select(available, count=2)
        strategy.reset()  # Не должно влиять на следующие выборы
        selected2 = strategy.select(available, count=2)
        strategy.reset()
        selected3 = strategy.select(available, count=2)

        # Все выборы корректны
        for selected in [selected1, selected2, selected3]:
            assert len(selected) == 2
            assert all(item in available for item in selected)


class TestRoundRobinStrategy:
    """Tests for round-robin selection strategy."""

    def test_empty_collection(self):
        """Test round-robin strategy with empty collection."""
        strategy = RoundRobinStrategy[str]()
        selected = strategy.select([], count=1)

        assert selected == []

    def test_initial_state(self):
        """Test round-robin strategy with initial state."""
        strategy = RoundRobinStrategy[str]()
        full_collection = ["a", "b", "c"]
        available = ["a", "b", "c"]

        selected = strategy.select(available, count=1, full_collection=full_collection)

        assert len(selected) == 1
        assert selected[0] in available
        assert selected == ["a"]  # First element of collection

    def test_sequential_selections(self):
        """Test sequential round-robin selections."""
        strategy = RoundRobinStrategy[str]()
        full_collection = ["a", "b", "c"]
        available = ["a", "b", "c"]

        selections = []

        for _ in range(6):  # 2 full cycles
            selected = strategy.select(
                available, count=1, full_collection=full_collection
            )
            selections.extend(selected)

        # Check cyclicity
        assert selections == ["a", "b", "c", "a", "b", "c"]

    def test_multiple_count(self):
        """Test round-robin with requesting multiple elements."""
        strategy = RoundRobinStrategy[str]()
        full_collection = ["a", "b", "c"]
        available = ["a", "b", "c"]

        selected = strategy.select(available, count=3, full_collection=full_collection)

        assert len(selected) == 3  # Round-robin returns requested count
        assert selected == ["a", "b", "c"]  # Sequential selection

    def test_partial_count(self):
        """Test round-robin with requesting part of elements."""
        strategy = RoundRobinStrategy[str]()
        full_collection = ["a", "b", "c", "d"]
        available = ["a", "b", "c", "d"]

        selected = strategy.select(available, count=2, full_collection=full_collection)

        assert len(selected) == 2
        assert selected == ["a", "b"]  # First two elements

    def test_partial_available_selection(self):
        """Test round-robin with partially available elements."""
        strategy = RoundRobinStrategy[str]()
        full_collection = ["a", "b", "c", "d", "e"]
        available = ["a", "c", "e"]  # Пропускаем b и d

        selections = []

        # Делаем несколько выборов
        for _ in range(6):
            selected = strategy.select(
                available, count=1, full_collection=full_collection
            )
            selections.extend(selected)

        # Должны получить цикл только из доступных элементов
        assert len(selections) == 6
        assert all(item in available for item in selections)
        # Проверяем, что все доступные элементы были выбраны
        assert set(selections) == set(available)

    def test_requires_full_collection(self):
        """Test that round-robin requires full_collection."""
        strategy = RoundRobinStrategy[str]()
        available = ["a", "b", "c"]

        with pytest.raises(ValueError, match="full_collection обязательна"):
            strategy.select(available, count=1)

    def test_state_persistence_with_partial_available(self):
        """Test state preservation when working with partial lists."""
        strategy = RoundRobinStrategy[str]()
        full_collection = ["alice", "bob", "charlie", "david"]

        # Первый выбор: все доступны
        available1 = ["alice", "bob", "charlie", "david"]
        selected1 = strategy.select(
            available1, count=1, full_collection=full_collection
        )
        assert selected1 == ["alice"]

        # Второй выбор: bob недоступен
        available2 = ["alice", "charlie", "david"]
        selected2 = strategy.select(
            available2, count=1, full_collection=full_collection
        )
        # Должен перейти к charlie (пропустив bob)
        assert selected2 == ["charlie"]

        # Третий выбор: все снова доступны
        available3 = ["alice", "bob", "charlie", "david"]
        selected3 = strategy.select(
            available3, count=1, full_collection=full_collection
        )
        # Должен выбрать david (следующий после charlie)
        assert selected3 == ["david"]

    def test_reset_state(self):
        """Test strategy state reset."""
        strategy = RoundRobinStrategy[str]()
        full_collection = ["a", "b", "c"]
        available = ["a", "b", "c"]

        # Делаем несколько выборов
        assert strategy.select(available, count=1, full_collection=full_collection) == [
            "a"
        ]
        assert strategy.select(available, count=1, full_collection=full_collection) == [
            "b"
        ]

        # Сбрасываем состояние
        strategy.reset()

        # Должен начать сначала
        assert strategy.select(available, count=1, full_collection=full_collection) == [
            "a"
        ]


class TestItemSelector:
    """Tests for ItemSelector class."""

    @pytest.fixture
    def sample_users(self) -> List[str]:
        """Fixture with example users."""
        return ["@alice", "@bob", "@charlie", "@david", "@eve"]

    def test_selector_initialization(self):
        """Test selector initialization."""
        selector = ItemSelector[str]()

        assert selector.collection == []
        assert selector.policy == SelectionPolicy.RANDOM

    def test_selector_set_collection(self, sample_users):
        """Test setting collection."""
        selector = ItemSelector[str]()
        selector.set_collection(sample_users)

        assert selector.collection == sample_users

    def test_selector_set_policy(self):
        """Test policy change."""
        selector = ItemSelector[str]()
        selector.set_collection(["a", "b", "c"])

        # Сначала Random
        assert selector.policy == SelectionPolicy.RANDOM

        # Меняем на RoundRobin
        selector.set_policy(SelectionPolicy.ROUND_ROBIN)
        assert selector.policy == SelectionPolicy.ROUND_ROBIN

        # Проверяем что новая стратегия работает
        result1 = selector.select(count=1)
        result2 = selector.select(count=1)
        assert result1 != result2  # Round-robin даёт разные результаты

    def test_selector_set_same_policy(self):
        """Test setting same policy (optimization - don't recreate strategy)."""
        selector = ItemSelector[str]()
        selector.set_collection(["a", "b", "c"])

        # Запоминаем текущую стратегию
        original_strategy = selector._strategy

        # Устанавливаем ту же политику
        selector.set_policy(SelectionPolicy.RANDOM)

        # Политика не изменилась, стратегия тоже не должна пересоздаваться
        assert selector.policy == SelectionPolicy.RANDOM
        assert selector._strategy is original_strategy  # Та же самая стратегия

    def test_selector_random_selection(self, sample_users):
        """Test random selection through selector."""
        selector = ItemSelector[str]()
        selector.set_collection(sample_users)
        selector.set_policy(SelectionPolicy.RANDOM)

        selected = selector.select(count=3)

        assert len(selected) == 3
        assert all(user in sample_users for user in selected)
        assert len(set(selected)) == 3  # Without repetitions

    def test_selector_round_robin_selection(self, sample_users):
        """Test round-robin selection through selector."""
        selector = ItemSelector[str]()
        selector.set_collection(sample_users)
        selector.set_policy(SelectionPolicy.ROUND_ROBIN)

        selections = []
        for _ in range(len(sample_users) * 2):  # 2 full cycles
            selected = selector.select(count=1)
            selections.extend(selected)

        # Check cyclicity
        expected = sample_users * 2
        assert selections == expected

    def test_selector_select_from_available_valid(self, sample_users):
        """Test selection from subset of available."""
        selector = ItemSelector[str]()
        selector.set_collection(sample_users)

        available = ["@alice", "@charlie", "@eve"]
        selected = selector.select_from_available(available, count=2)

        assert len(selected) <= 2
        assert all(user in available for user in selected)

    def test_selector_select_from_available_invalid(self, sample_users):
        """Test selection from subset with elements not from collection."""
        selector = ItemSelector[str]()
        selector.set_collection(sample_users)

        available = ["@alice", "@unknown_user"]  # unknown_user не в коллекции

        with pytest.raises(ValueError, match="не найден в коллекции"):
            selector.select_from_available(available, count=1)

    def test_selector_select_from_empty_available(self, sample_users):
        """Test selection from empty subset."""
        selector = ItemSelector[str]()
        selector.set_collection(sample_users)

        selected = selector.select_from_available([], count=3)

        assert selected == []

    def test_selector_select_empty_collection(self):
        """Test selection from empty collection."""
        selector = ItemSelector[str]()

        selected = selector.select(count=5)

        assert selected == []

    def test_selector_reset_state(self, sample_users):
        """Test state reset."""
        selector = ItemSelector[str]()
        selector.set_collection(sample_users)
        selector.set_policy(SelectionPolicy.ROUND_ROBIN)

        # Делаем выборы - проверяем что reset работает
        result1 = selector.select(count=1)
        result2 = selector.select(count=1)

        # Сбрасываем состояние
        selector.reset_state()

        # После сброса должен начать сначала
        result3 = selector.select(count=1)
        assert result3 == result1  # Начинает сначала

    def test_selector_get_info(self, sample_users):
        """Test getting selector information."""
        selector = ItemSelector[str]()
        selector.set_collection(sample_users)
        selector.set_policy(SelectionPolicy.ROUND_ROBIN)

        info = selector.get_info()

        assert info["collection_size"] == len(sample_users)
        assert info["policy"] == SelectionPolicy.ROUND_ROBIN.value
        assert len(info) == 2  # Только размер коллекции и политика

    def test_selector_unsupported_policy(self):
        """Test unsupported policy."""
        selector = ItemSelector[str]()

        # Напрямую устанавливаем недопустимую политику
        selector.policy = "invalid_policy"  # type: ignore

        with pytest.raises(ValueError, match="Неподдерживаемая политика"):
            selector._create_strategy()


class TestIntegrationScenarios:
    """Integration tests for real usage scenarios."""

    def test_telegram_bot_scenario(self):
        """Test Telegram bot usage scenario."""
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

        # Check cyclicity в рамках активных
        all_assigned = [assigned1[0], assigned2[0], assigned3[0], assigned4[0]]
        assert len(set(all_assigned)) <= len(active_today)

        # Сценарий 2: Random назначение
        selector.set_policy(SelectionPolicy.RANDOM)

        assigned_random = selector.select_from_available(active_today, count=2)
        assert len(assigned_random) == 2
        assert all(user in active_today for user in assigned_random)

    def test_state_persistence_across_selections(self):
        """Test state preservation between selections."""
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
        expected = users * 2  # 2 full cycles
        assert results == expected

    @patch("assign_bot.selector.random.sample")
    def test_random_selection_deterministic(self, mock_sample):
        """Test deterministic random selection behavior (for predictable tests)."""
        mock_sample.return_value = ["@bob", "@alice"]

        selector = ItemSelector[str]()
        selector.set_collection(["@alice", "@bob", "@charlie"])
        selector.set_policy(SelectionPolicy.RANDOM)

        selected = selector.select(count=2)

        assert selected == ["@bob", "@alice"]
        mock_sample.assert_called_once_with(["@alice", "@bob", "@charlie"], k=2)


@pytest.mark.parametrize(
    "policy,count,expected_count",
    [
        (SelectionPolicy.RANDOM, 2, 2),
        (SelectionPolicy.ROUND_ROBIN, 3, 3),
        (SelectionPolicy.ROUND_ROBIN, 2, 2),
    ],
)
def test_policy_specific_behavior(policy, count, expected_count):
    """Parameterized test of different policies behavior."""
    users = ["@user1", "@user2", "@user3", "@user4"]
    selector = ItemSelector[str]()
    selector.set_collection(users)
    selector.set_policy(policy)

    selected = selector.select(count=count)
    assert len(selected) == expected_count
