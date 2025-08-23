"""
Integration tests for bot using new selector module.

Verifies correct integration of selector into bot logic.
"""

import pytest
from unittest.mock import Mock, AsyncMock
from typing import List

from assign_bot.bot import (
    UserConfig,
    _select_assignees,
    _get_chat_state,
    DEFAULT_USERNAMES,
    CHAT_STATE,
)
from assign_bot.selector import SelectionPolicy


class TestUserConfig:
    """Tests for UserConfig class with selector."""

    def test_user_config_initialization(self):
        """Test user configuration initialization."""
        config = UserConfig()

        assert config.usernames == []
        assert config.selector.collection == []
        assert config.selector.policy == SelectionPolicy.RANDOM

    def test_user_config_with_usernames(self):
        """Test configuration with initial users."""
        usernames = ["@alice", "@bob", "@charlie"]
        config = UserConfig()
        config.usernames = usernames
        config.selector.set_collection(usernames)

        assert config.usernames == usernames
        assert config.selector.collection == usernames


class TestSelectAssignees:
    """Tests for _select_assignees function."""

    @pytest.fixture
    def mock_state(self) -> UserConfig:
        """Fixture with mock state."""
        state = UserConfig()
        usernames = ["@alice", "@bob", "@charlie", "@david"]
        state.usernames = usernames
        state.selector.set_collection(usernames)
        return state

    def test_select_assignees_empty_active(self, mock_state):
        """Test selection with empty active list."""
        result = _select_assignees(SelectionPolicy.RANDOM, [], mock_state, 2)

        assert result == []

    def test_select_assignees_random_policy(self, mock_state):
        """Test selection with RANDOM policy."""
        active = ["@alice", "@charlie"]

        result = _select_assignees(SelectionPolicy.RANDOM, active, mock_state, 2)

        # For 2-person team select 2
        assert len(result) == 2
        assert all(user in active for user in result)
        assert mock_state.selector.policy == SelectionPolicy.RANDOM

    def test_select_assignees_random_policy_large_team(self, mock_state):
        """Test selection with RANDOM policy for large team."""
        active = ["@alice", "@bob", "@charlie"]  # >= 2 people

        result = _select_assignees(SelectionPolicy.RANDOM, active, mock_state, 2)

        # For team >= 2 people select 2
        assert len(result) == 2
        assert all(user in active for user in result)

    def test_select_assignees_random_policy_small_team(self, mock_state):
        """Test selection with RANDOM policy for small team."""
        active = ["@alice"]  # < 2 people

        result = _select_assignees(SelectionPolicy.RANDOM, active, mock_state, 1)

        # For team < 2 people select 1
        assert len(result) == 1
        assert result[0] in active

    def test_select_assignees_round_robin_policy(self, mock_state):
        """Test selection with ROUND_ROBIN policy."""
        active = ["@alice", "@charlie", "@david"]

        result = _select_assignees(SelectionPolicy.ROUND_ROBIN, active, mock_state, 2)

        # Round-robin for team >= 2 selects 2 people
        assert len(result) == 2
        assert all(user in active for user in result)
        assert mock_state.selector.policy == SelectionPolicy.ROUND_ROBIN

    def test_select_assignees_round_robin_sequence(self, mock_state):
        """Test round-robin selection sequence."""
        active = ["@alice", "@bob", "@charlie"]

        results = []
        for _ in range(3):  # 3 selections
            result = _select_assignees(
                SelectionPolicy.ROUND_ROBIN, active, mock_state, 2
            )
            results.extend(result)

        # Each selection returns 2 participants, total 6 results
        assert len(results) == 6
        # Check that all participants are used (not necessarily evenly)
        assert len(set(results)) == 3  # All 3 users should be selected

    def test_select_assignees_with_invalid_active_users(self, mock_state):
        """Test selection with active users not from collection."""
        # Active users contain someone not in state.usernames
        active = ["@alice", "@unknown_user"]

        # Function should handle error and filter valid users
        result = _select_assignees(SelectionPolicy.RANDOM, active, mock_state, 2)

        # Should select only valid users (only @alice)
        assert len(result) == 1
        assert result[0] == "@alice"
        # Check that collection was reset
        assert mock_state.selector.collection == mock_state.usernames


class TestChatState:
    """Tests for chat state management."""

    def setup_method(self):
        """Clean state before each test."""
        CHAT_STATE.clear()

    def test_get_chat_state_new_chat(self):
        """Test getting state for new chat."""
        chat_id = 12345

        state = _get_chat_state(chat_id)

        assert isinstance(state, UserConfig)
        assert state.usernames == []
        assert state.selector.collection == []
        assert chat_id in CHAT_STATE

    def test_get_chat_state_existing_chat(self):
        """Test getting state for existing chat."""
        chat_id = 12345
        # Создаём состояние
        first_state = _get_chat_state(chat_id)
        first_state.usernames = ["@test_user"]

        # Получаем то же состояние
        second_state = _get_chat_state(chat_id)

        assert second_state is first_state
        assert second_state.usernames == ["@test_user"]


class TestDefaultUsers:
    """Tests for working with default users."""

    def test_default_usernames_constant(self):
        """Test default users constant."""
        assert isinstance(DEFAULT_USERNAMES, list)
        assert len(DEFAULT_USERNAMES) > 0
        assert all(username.startswith("@") for username in DEFAULT_USERNAMES)

        # Проверяем конкретных пользователей из требований
        expected_users = {
            "@MaksimMukhametov",
            "@jellex",
            "@vSmykovsky",
            "@RomanDobrov",
            "@gergoltz",
        }
        assert set(DEFAULT_USERNAMES) == expected_users


class TestIntegrationFlows:
    """Integration tests for full flows."""

    def setup_method(self):
        """Clean state before each test."""
        CHAT_STATE.clear()

    def test_full_assignment_flow_round_robin(self):
        """Test full assignment flow with round-robin."""
        chat_id = 12345

        # 1. Получаем состояние чата (новый чат)
        state = _get_chat_state(chat_id)
        assert state.usernames == []

        # 2. Устанавливаем участников (имитируем /configure)
        usernames = ["@alice", "@bob", "@charlie"]
        state.usernames = usernames
        state.selector.set_collection(usernames)

        # 3. Выполняем назначения (имитируем /assign)
        active_users = ["@alice", "@charlie"]  # Bob не активен сегодня

        # Несколько назначений подряд
        assignments = []
        for _ in range(4):
            assigned = _select_assignees(
                SelectionPolicy.ROUND_ROBIN, active_users, state, 2
            )
            assignments.extend(assigned)

        # Проверяем результаты
        assert len(assignments) == 8  # 4 назначения по 2 человека = 8
        assert all(user in active_users for user in assignments)
        # Должна быть цикличность между @alice и @charlie
        unique_assigned = set(assignments)
        assert unique_assigned.issubset(set(active_users))

    def test_full_assignment_flow_random(self):
        """Test full assignment flow with random."""
        chat_id = 67890

        # 1. Получаем состояние чата
        state = _get_chat_state(chat_id)

        # 2. Устанавливаем участников
        usernames = ["@user1", "@user2", "@user3", "@user4"]
        state.usernames = usernames
        state.selector.set_collection(usernames)

        # 3. Выполняем random назначение
        active_users = usernames  # Все активны

        assigned = _select_assignees(SelectionPolicy.RANDOM, active_users, state, 2)

        # Для команды >= 2 должно выбрать 2 человек
        assert len(assigned) == 2
        assert all(user in active_users for user in assigned)
        assert len(set(assigned)) == 2  # Без дубликатов

    def test_policy_switch_during_usage(self):
        """Test policy switching during usage."""
        chat_id = 111222
        state = _get_chat_state(chat_id)

        usernames = ["@a", "@b", "@c"]
        state.usernames = usernames
        state.selector.set_collection(usernames)

        active = ["@a", "@c"]

        # Начинаем с round-robin
        rr_result = _select_assignees(SelectionPolicy.ROUND_ROBIN, active, state, 2)
        assert len(rr_result) == 2  # Для 2 активных выберет 2

        # Переключаемся на random
        random_result = _select_assignees(SelectionPolicy.RANDOM, active, state, 2)
        assert len(random_result) == 2  # Для 2 активных выберет 2

        # Возвращаемся к round-robin (состояние должно сброситься)
        rr_result2 = _select_assignees(SelectionPolicy.ROUND_ROBIN, active, state, 2)
        assert len(rr_result2) == 2  # Для 2 активных выберет 2


class TestRealWorldScenarios:
    """Tests for real-world usage scenarios."""

    def setup_method(self):
        """Clean state before each test."""
        CHAT_STATE.clear()

    def test_weekly_duty_assignment(self):
        """Test weekly duty assignment scenario."""
        chat_id = 999
        state = _get_chat_state(chat_id)

        # Команда разработки
        team = ["@dev1", "@dev2", "@dev3", "@dev4", "@dev5"]
        state.usernames = team
        state.selector.set_collection(team)

        # Каждую неделю назначаем дежурного (round-robin)
        weekly_assignments = []
        for week in range(10):  # 10 недель
            # Иногда кто-то в отпуске
            if week == 3:
                active = ["@dev1", "@dev2", "@dev4"]  # dev3, dev5 в отпуске
            elif week == 7:
                active = ["@dev2", "@dev3", "@dev4", "@dev5"]  # dev1 в отпуске
            else:
                active = team

            assigned = _select_assignees(SelectionPolicy.ROUND_ROBIN, active, state, 1)
            weekly_assignments.append((week, assigned[0] if assigned else None))

        # Проверяем, что никто не пропущен надолго
        assigned_users = [user for week, user in weekly_assignments if user]
        assert (
            len(set(assigned_users)) >= 3
        )  # Минимум 3 разных пользователя за 10 недель

    def test_random_task_distribution(self):
        """Test random task distribution."""
        chat_id = 888
        state = _get_chat_state(chat_id)

        team = ["@qa1", "@qa2", "@qa3", "@qa4"]
        state.usernames = team
        state.selector.set_collection(team)

        # Распределяем задачи случайно (по 2 человека на задачу)
        task_assignments = []
        for task_id in range(5):
            assigned = _select_assignees(SelectionPolicy.RANDOM, team, state, 2)
            task_assignments.append((task_id, assigned))

        # Проверяем разнообразие
        all_assigned = []
        for task_id, assigned in task_assignments:
            all_assigned.extend(assigned)

        # Каждый должен получить задачи
        unique_assigned = set(all_assigned)
        assert len(unique_assigned) >= 2  # Минимум 2 разных человека получили задачи
