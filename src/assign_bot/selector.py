"""
Module for selecting elements from collection with various strategies.

Provides universal ItemSelector class for selecting N elements
from a pre-configured collection with support for different selection policies.
"""

from __future__ import annotations

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Generic, List, Optional, Sequence, TypeVar

T = TypeVar("T")


class SelectionPolicy(str, Enum):
    """Policies for selecting elements from collection."""

    ROUND_ROBIN = "round_robin"
    RANDOM = "random"


class SelectionStrategy(ABC, Generic[T]):
    """Abstract strategy for selecting elements."""

    @abstractmethod
    def select(self, available: Sequence[T], count: int, **kwargs) -> List[T]:
        """
        Selects elements from available ones.

        Args:
            available: Available elements for selection
            count: Number of elements to select
            **kwargs: Additional parameters for strategy

        Returns:
            List of selected elements
        """
        pass

    @abstractmethod
    def reset(self) -> None:
        """Resets internal state of the strategy."""
        pass


class RandomStrategy(SelectionStrategy[T]):
    """Random selection strategy."""

    def select(self, available: Sequence[T], count: int, **kwargs) -> List[T]:
        """Selects random elements without repetition."""
        if not available:
            return []

        actual_count = min(count, len(available))
        selected = random.sample(list(available), k=actual_count)
        return selected

    def reset(self) -> None:
        """Resets state. RandomStrategy has no state."""
        pass


class RoundRobinStrategy(SelectionStrategy[T]):
    """Round-robin selection strategy with internal state."""

    def __init__(self) -> None:
        """Initialize strategy with internal state."""
        self._state: Optional[int] = None

    def select(self, available: Sequence[T], count: int, **kwargs) -> List[T]:
        """
        Selects elements by round-robin considering full collection.

        Args:
            available: Available elements for selection (subset of full_collection)
            count: Number of elements to select
            **kwargs: Must contain 'full_collection' - full collection of elements

        Returns:
            List of selected elements

        Raises:
            ValueError: If full_collection is not provided
        """
        if not available:
            return []

        if self._state is None:
            self._state = -1

        full_collection = kwargs.get("full_collection")
        if full_collection is None:
            raise ValueError("full_collection is required for RoundRobinStrategy")

        selected = []
        actual_count = min(count, len(available))
        available_set = set(available)

        # Search for next available elements in full collection
        attempts = 0
        max_attempts = len(full_collection) * 2  # Protection from infinite loop

        while len(selected) < actual_count and attempts < max_attempts:
            attempts += 1
            self._state = (self._state + 1) % len(full_collection)
            candidate = full_collection[self._state]

            if candidate in available_set:
                selected.append(candidate)

        return selected

    def reset(self) -> None:
        """Resets internal round-robin state."""
        self._state = None


class StrategyMapper:
    """Mapper for creating selection strategies by policy."""

    @staticmethod
    def create_strategy(policy: SelectionPolicy) -> SelectionStrategy[Any]:
        """
        Creates selection strategy for given policy.

        Args:
            policy: Selection policy

        Returns:
            Instance of corresponding strategy

        Raises:
            ValueError: If policy is not supported
        """
        strategy_map = {
            SelectionPolicy.RANDOM: RandomStrategy,
            SelectionPolicy.ROUND_ROBIN: RoundRobinStrategy,
        }

        strategy_class = strategy_map.get(policy)
        if strategy_class is None:
            raise ValueError(f"Unsupported policy: {policy}")

        return strategy_class()

    @staticmethod
    def get_strategy_kwargs(
        policy: SelectionPolicy, full_collection: Sequence = None
    ) -> dict:
        """
        Returns additional parameters for strategy.

        Args:
            policy: Selection policy
            full_collection: Full collection (for round-robin)

        Returns:
            Dictionary with parameters for passing to strategy.select()
        """
        if policy == SelectionPolicy.ROUND_ROBIN:
            return {"full_collection": full_collection}
        return {}


@dataclass
class ItemSelector(Generic[T]):
    """
    Universal element selector with support for various strategies.

    Attributes:
        collection: Full collection of elements
        policy: Selection policy
    """

    collection: List[T] = field(default_factory=list)
    policy: SelectionPolicy = SelectionPolicy.RANDOM

    def __post_init__(self) -> None:
        """Initialize strategy based on policy."""
        self._strategy = self._create_strategy()

    def _create_strategy(self) -> SelectionStrategy[T]:
        """Creates strategy based on current policy."""
        return StrategyMapper.create_strategy(self.policy)

    def set_collection(self, items: Sequence[T]) -> None:
        """Sets collection of elements."""
        self.collection = list(items)
        # Reset strategy state when collection changes
        self._strategy.reset()

    def set_policy(self, policy: SelectionPolicy) -> None:
        """Changes selection policy."""
        if self.policy != policy:
            self.policy = policy
            self._strategy = self._create_strategy()
            # When policy changes, new strategy is created with clean state

    def select_from_available(self, available: Sequence[T], count: int = 1) -> List[T]:
        """
        Selects elements from subset of available ones.

        Args:
            available: Subset of elements for selection (must be from collection)
            count: Number of elements to select

        Returns:
            List of selected elements

        Raises:
            ValueError: If available contains elements not from collection
        """
        if not available:
            return []

        # Check that all available elements are in collection
        collection_set = set(self.collection)
        for item in available:
            if item not in collection_set:
                raise ValueError(f"Element {item} not found in collection")

        # Get additional parameters for strategy
        strategy_kwargs = StrategyMapper.get_strategy_kwargs(
            self.policy, full_collection=self.collection
        )

        # Perform selection - strategy manages state itself
        selected = self._strategy.select(available, count, **strategy_kwargs)

        return selected

    def select(self, count: int = 1) -> List[T]:
        """
        Selects elements from entire collection.

        Args:
            count: Number of elements to select

        Returns:
            List of selected elements
        """
        return self.select_from_available(self.collection, count)

    def reset_state(self) -> None:
        """Resets internal state of strategy."""
        self._strategy.reset()

    def get_info(self) -> dict[str, Any]:
        """Returns information about current selector state."""
        return {
            "collection_size": len(self.collection),
            "policy": self.policy.value,
        }
