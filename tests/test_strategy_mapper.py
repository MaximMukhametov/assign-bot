"""
Tests for StrategyMapper.

Verifies correct mapping of policies to strategies.
"""

import pytest

from assign_bot.selector import (
    StrategyMapper,
    SelectionPolicy,
    RandomStrategy,
    RoundRobinStrategy,
)


class TestStrategyMapper:
    """Tests for StrategyMapper class."""

    def test_create_random_strategy(self):
        """Test creating Random strategy."""
        strategy = StrategyMapper.create_strategy(SelectionPolicy.RANDOM)

        assert isinstance(strategy, RandomStrategy)

    def test_create_round_robin_strategy(self):
        """Test creating Round-Robin strategy."""
        strategy = StrategyMapper.create_strategy(SelectionPolicy.ROUND_ROBIN)

        assert isinstance(strategy, RoundRobinStrategy)

    def test_create_strategy_unsupported_policy(self):
        """Test creating strategy for unsupported policy."""
        # Create non-existent policy for test
        fake_policy = "unsupported_policy"

        with pytest.raises(ValueError, match="Unsupported policy"):
            StrategyMapper.create_strategy(fake_policy)  # type: ignore

    def test_get_strategy_kwargs_random(self):
        """Test getting kwargs for Random strategy."""
        kwargs = StrategyMapper.get_strategy_kwargs(
            SelectionPolicy.RANDOM, full_collection=["a", "b", "c"]
        )

        assert kwargs == {}  # Random doesn't need additional parameters

    def test_get_strategy_kwargs_round_robin(self):
        """Test getting kwargs for Round-Robin strategy."""
        full_collection = ["@alice", "@bob", "@charlie"]
        kwargs = StrategyMapper.get_strategy_kwargs(
            SelectionPolicy.ROUND_ROBIN, full_collection=full_collection
        )

        assert kwargs == {"full_collection": full_collection}

    def test_get_strategy_kwargs_round_robin_no_collection(self):
        """Test getting kwargs for Round-Robin without collection."""
        kwargs = StrategyMapper.get_strategy_kwargs(
            SelectionPolicy.ROUND_ROBIN, full_collection=None
        )

        assert kwargs == {"full_collection": None}

    def test_strategy_creation_and_usage_integration(self):
        """Integration test: strategy creation and usage."""
        # Create strategy through mapper
        strategy = StrategyMapper.create_strategy(SelectionPolicy.ROUND_ROBIN)

        # Get parameters through mapper
        full_collection = ["@user1", "@user2", "@user3"]
        kwargs = StrategyMapper.get_strategy_kwargs(
            SelectionPolicy.ROUND_ROBIN, full_collection=full_collection
        )

        # Use strategy
        available = ["@user1", "@user3"]  # user2 unavailable
        selected = strategy.select(available, count=1, **kwargs)

        assert len(selected) == 1
        assert selected[0] in available

    def test_mapper_supports_all_policies(self):
        """Test that mapper supports all defined policies."""
        # Get all policies from enum
        all_policies = list(SelectionPolicy)

        # Check that strategy can be created for each policy
        for policy in all_policies:
            strategy = StrategyMapper.create_strategy(policy)
            assert strategy is not None

            # Check that kwargs can be obtained
            kwargs = StrategyMapper.get_strategy_kwargs(
                policy, full_collection=["test"]
            )
            assert isinstance(kwargs, dict)


class TestStrategyMapperExtensibility:
    """Tests for StrategyMapper extensibility."""

    def test_mapper_is_easily_extensible(self):
        """Demonstration of how easy it is to extend mapper."""
        # This test shows how easy it is to add new strategy
        # Just need to add entry in strategy_map and case in get_strategy_kwargs

        # Check current number of supported policies
        current_policies = list(SelectionPolicy)
        supported_policies = []

        for policy in current_policies:
            try:
                StrategyMapper.create_strategy(policy)
                supported_policies.append(policy)
            except ValueError:
                pass

        # All defined policies should be supported
        assert len(supported_policies) == len(current_policies)
        assert set(supported_policies) == set(current_policies)
