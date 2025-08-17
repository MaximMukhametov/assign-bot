"""
Тесты для StrategyMapper.

Проверяет корректность маппинга политик на стратегии.
"""

import pytest

from assign_bot.selector import (
    StrategyMapper,
    SelectionPolicy,
    RandomStrategy,
    RoundRobinStrategy,
)


class TestStrategyMapper:
    """Тесты для класса StrategyMapper."""

    def test_create_random_strategy(self):
        """Тест создания стратегии Random."""
        strategy = StrategyMapper.create_strategy(SelectionPolicy.RANDOM)

        assert isinstance(strategy, RandomStrategy)

    def test_create_round_robin_strategy(self):
        """Тест создания стратегии Round-Robin."""
        strategy = StrategyMapper.create_strategy(SelectionPolicy.ROUND_ROBIN)

        assert isinstance(strategy, RoundRobinStrategy)

    def test_create_strategy_unsupported_policy(self):
        """Тест создания стратегии для неподдерживаемой политики."""
        # Создаём несуществующую политику для теста
        fake_policy = "unsupported_policy"

        with pytest.raises(ValueError, match="Неподдерживаемая политика"):
            StrategyMapper.create_strategy(fake_policy)  # type: ignore

    def test_get_strategy_kwargs_random(self):
        """Тест получения kwargs для Random стратегии."""
        kwargs = StrategyMapper.get_strategy_kwargs(
            SelectionPolicy.RANDOM, full_collection=["a", "b", "c"]
        )

        assert kwargs == {}  # Random не нуждается в дополнительных параметрах

    def test_get_strategy_kwargs_round_robin(self):
        """Тест получения kwargs для Round-Robin стратегии."""
        full_collection = ["@alice", "@bob", "@charlie"]
        kwargs = StrategyMapper.get_strategy_kwargs(
            SelectionPolicy.ROUND_ROBIN, full_collection=full_collection
        )

        assert kwargs == {"full_collection": full_collection}

    def test_get_strategy_kwargs_round_robin_no_collection(self):
        """Тест получения kwargs для Round-Robin без коллекции."""
        kwargs = StrategyMapper.get_strategy_kwargs(
            SelectionPolicy.ROUND_ROBIN, full_collection=None
        )

        assert kwargs == {"full_collection": None}

    def test_strategy_creation_and_usage_integration(self):
        """Интеграционный тест: создание стратегии и её использование."""
        # Создаём стратегию через маппер
        strategy = StrategyMapper.create_strategy(SelectionPolicy.ROUND_ROBIN)

        # Получаем параметры через маппер
        full_collection = ["@user1", "@user2", "@user3"]
        kwargs = StrategyMapper.get_strategy_kwargs(
            SelectionPolicy.ROUND_ROBIN, full_collection=full_collection
        )

        # Используем стратегию
        available = ["@user1", "@user3"]  # user2 недоступен
        selected = strategy.select(available, count=1, **kwargs)

        assert len(selected) == 1
        assert selected[0] in available

    def test_mapper_supports_all_policies(self):
        """Тест что маппер поддерживает все определённые политики."""
        # Получаем все политики из enum
        all_policies = list(SelectionPolicy)

        # Проверяем, что для каждой политики можно создать стратегию
        for policy in all_policies:
            strategy = StrategyMapper.create_strategy(policy)
            assert strategy is not None

            # Проверяем, что можно получить kwargs
            kwargs = StrategyMapper.get_strategy_kwargs(
                policy, full_collection=["test"]
            )
            assert isinstance(kwargs, dict)


class TestStrategyMapperExtensibility:
    """Тесты расширяемости StrategyMapper."""

    def test_mapper_is_easily_extensible(self):
        """Демонстрация того, как легко расширить маппер."""
        # Этот тест показывает, как просто добавить новую стратегию
        # Достаточно добавить запись в strategy_map и case в get_strategy_kwargs

        # Проверяем текущее количество поддерживаемых политик
        current_policies = list(SelectionPolicy)
        supported_policies = []

        for policy in current_policies:
            try:
                StrategyMapper.create_strategy(policy)
                supported_policies.append(policy)
            except ValueError:
                pass

        # Все определённые политики должны поддерживаться
        assert len(supported_policies) == len(current_policies)
        assert set(supported_policies) == set(current_policies)
