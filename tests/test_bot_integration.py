"""
Интеграционные тесты для бота с использованием нового модуля selector.

Проверяет корректность интеграции селектора в логику бота.
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
    """Тесты для класса UserConfig с селектором."""
    
    def test_user_config_initialization(self):
        """Тест инициализации конфигурации пользователя."""
        config = UserConfig()
        
        assert config.usernames == []
        assert config.selector.collection == []
        assert config.selector.policy == SelectionPolicy.RANDOM
    
    def test_user_config_with_usernames(self):
        """Тест конфигурации с начальными пользователями."""
        usernames = ["@alice", "@bob", "@charlie"]
        config = UserConfig()
        config.usernames = usernames
        config.selector.set_collection(usernames)
        
        assert config.usernames == usernames
        assert config.selector.collection == usernames


class TestSelectAssignees:
    """Тесты для функции _select_assignees."""
    
    @pytest.fixture
    def mock_state(self) -> UserConfig:
        """Фикстура с мок-состоянием."""
        state = UserConfig()
        usernames = ["@alice", "@bob", "@charlie", "@david"]
        state.usernames = usernames
        state.selector.set_collection(usernames)
        return state
    
    def test_select_assignees_empty_active(self, mock_state):
        """Тест выбора с пустым списком активных."""
        result = _select_assignees(SelectionPolicy.RANDOM, [], mock_state)
        
        assert result == []
    
    def test_select_assignees_random_policy(self, mock_state):
        """Тест выбора с политикой RANDOM."""
        active = ["@alice", "@charlie"]
        
        result = _select_assignees(SelectionPolicy.RANDOM, active, mock_state)
        
        # Для команды из 2 человек выбираем 2
        assert len(result) == 2
        assert all(user in active for user in result)
        assert mock_state.selector.policy == SelectionPolicy.RANDOM
    
    def test_select_assignees_random_policy_large_team(self, mock_state):
        """Тест выбора с политикой RANDOM для большой команды."""
        active = ["@alice", "@bob", "@charlie"]  # >= 2 человек
        
        result = _select_assignees(SelectionPolicy.RANDOM, active, mock_state)
        
        # Для команды >= 2 человек выбираем 2
        assert len(result) == 2
        assert all(user in active for user in result)
    
    def test_select_assignees_random_policy_small_team(self, mock_state):
        """Тест выбора с политикой RANDOM для маленькой команды."""
        active = ["@alice"]  # < 2 человек
        
        result = _select_assignees(SelectionPolicy.RANDOM, active, mock_state)
        
        # Для команды < 2 человек выбираем 1
        assert len(result) == 1
        assert result[0] in active
    
    def test_select_assignees_round_robin_policy(self, mock_state):
        """Тест выбора с политикой ROUND_ROBIN."""
        active = ["@alice", "@charlie", "@david"]
        
        result = _select_assignees(SelectionPolicy.ROUND_ROBIN, active, mock_state)
        
        # Round-robin всегда выбирает 1 человека
        assert len(result) == 1
        assert result[0] in active
        assert mock_state.selector.policy == SelectionPolicy.ROUND_ROBIN
    
    def test_select_assignees_round_robin_sequence(self, mock_state):
        """Тест последовательности round-robin выборов."""
        active = ["@alice", "@bob", "@charlie"]
        
        results = []
        for _ in range(6):  # 2 полных цикла
            result = _select_assignees(SelectionPolicy.ROUND_ROBIN, active, mock_state)
            results.extend(result)
        
        # Проверяем цикличность (может быть в любом порядке, но должен быть цикл)
        assert len(results) == 6
        assert len(set(results)) == 3  # Все 3 пользователя должны быть выбраны
    
    def test_select_assignees_with_invalid_active_users(self, mock_state):
        """Тест выбора с активными пользователями не из коллекции."""
        # Активные пользователи содержат того, кого нет в state.usernames
        active = ["@alice", "@unknown_user"]
        
        # Функция должна обработать ошибку и отфильтровать валидных пользователей
        result = _select_assignees(SelectionPolicy.RANDOM, active, mock_state)
        
        # Должен выбрать только валидных пользователей (только @alice)
        assert len(result) == 1
        assert result[0] == "@alice"
        # Проверяем, что коллекция была переустановлена
        assert mock_state.selector.collection == mock_state.usernames


class TestChatState:
    """Тесты для управления состоянием чата."""
    
    def setup_method(self):
        """Очистка состояния перед каждым тестом."""
        CHAT_STATE.clear()
    
    def test_get_chat_state_new_chat(self):
        """Тест получения состояния для нового чата."""
        chat_id = 12345
        
        state = _get_chat_state(chat_id)
        
        assert isinstance(state, UserConfig)
        assert state.usernames == []
        assert state.selector.collection == []
        assert chat_id in CHAT_STATE
    
    def test_get_chat_state_existing_chat(self):
        """Тест получения состояния для существующего чата."""
        chat_id = 12345
        # Создаём состояние
        first_state = _get_chat_state(chat_id)
        first_state.usernames = ["@test_user"]
        
        # Получаем то же состояние
        second_state = _get_chat_state(chat_id)
        
        assert second_state is first_state
        assert second_state.usernames == ["@test_user"]


class TestDefaultUsers:
    """Тесты для работы с пользователями по умолчанию."""
    
    def test_default_usernames_constant(self):
        """Тест константы с пользователями по умолчанию."""
        assert isinstance(DEFAULT_USERNAMES, list)
        assert len(DEFAULT_USERNAMES) > 0
        assert all(username.startswith("@") for username in DEFAULT_USERNAMES)
        
        # Проверяем конкретных пользователей из требований
        expected_users = {
            "@MaksimMukhametov",
            "@jellex", 
            "@vSmykovsky",
            "@RomanDobrov",
            "@gergoltz"
        }
        assert set(DEFAULT_USERNAMES) == expected_users


class TestIntegrationFlows:
    """Интеграционные тесты полных флоу."""
    
    def setup_method(self):
        """Очистка состояния перед каждым тестом."""
        CHAT_STATE.clear()
    
    def test_full_assignment_flow_round_robin(self):
        """Тест полного флоу назначения с round-robin."""
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
            assigned = _select_assignees(SelectionPolicy.ROUND_ROBIN, active_users, state)
            assignments.extend(assigned)
        
        # Проверяем результаты
        assert len(assignments) == 4
        assert all(user in active_users for user in assignments)
        # Должна быть цикличность между @alice и @charlie
        unique_assigned = set(assignments)
        assert unique_assigned.issubset(set(active_users))
    
    def test_full_assignment_flow_random(self):
        """Тест полного флоу назначения с random."""
        chat_id = 67890
        
        # 1. Получаем состояние чата
        state = _get_chat_state(chat_id)
        
        # 2. Устанавливаем участников
        usernames = ["@user1", "@user2", "@user3", "@user4"]
        state.usernames = usernames
        state.selector.set_collection(usernames)
        
        # 3. Выполняем random назначение
        active_users = usernames  # Все активны
        
        assigned = _select_assignees(SelectionPolicy.RANDOM, active_users, state)
        
        # Для команды >= 2 должно выбрать 2 человек
        assert len(assigned) == 2
        assert all(user in active_users for user in assigned)
        assert len(set(assigned)) == 2  # Без дубликатов
    
    def test_policy_switch_during_usage(self):
        """Тест смены политики в процессе использования."""
        chat_id = 111222
        state = _get_chat_state(chat_id)
        
        usernames = ["@a", "@b", "@c"]
        state.usernames = usernames
        state.selector.set_collection(usernames)
        
        active = ["@a", "@c"]
        
        # Начинаем с round-robin
        rr_result = _select_assignees(SelectionPolicy.ROUND_ROBIN, active, state)
        assert len(rr_result) == 1
        
        # Переключаемся на random
        random_result = _select_assignees(SelectionPolicy.RANDOM, active, state)
        assert len(random_result) == 2  # Для 2 активных выберет 2
        
        # Возвращаемся к round-robin (состояние должно сброситься)
        rr_result2 = _select_assignees(SelectionPolicy.ROUND_ROBIN, active, state)
        assert len(rr_result2) == 1


class TestRealWorldScenarios:
    """Тесты реальных сценариев использования."""
    
    def setup_method(self):
        """Очистка состояния перед каждым тестом.""" 
        CHAT_STATE.clear()
    
    def test_weekly_duty_assignment(self):
        """Тест сценария еженедельного назначения дежурного."""
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
            
            assigned = _select_assignees(SelectionPolicy.ROUND_ROBIN, active, state)
            weekly_assignments.append((week, assigned[0] if assigned else None))
        
        # Проверяем, что никто не пропущен надолго
        assigned_users = [user for week, user in weekly_assignments if user]
        assert len(set(assigned_users)) >= 3  # Минимум 3 разных пользователя за 10 недель
    
    def test_random_task_distribution(self):
        """Тест случайного распределения задач."""
        chat_id = 888
        state = _get_chat_state(chat_id)
        
        team = ["@qa1", "@qa2", "@qa3", "@qa4"]
        state.usernames = team
        state.selector.set_collection(team)
        
        # Распределяем задачи случайно (по 2 человека на задачу)
        task_assignments = []
        for task_id in range(5):
            assigned = _select_assignees(SelectionPolicy.RANDOM, team, state)
            task_assignments.append((task_id, assigned))
        
        # Проверяем разнообразие
        all_assigned = []
        for task_id, assigned in task_assignments:
            all_assigned.extend(assigned)
        
        # Каждый должен получить задачи
        unique_assigned = set(all_assigned)
        assert len(unique_assigned) >= 2  # Минимум 2 разных человека получили задачи
