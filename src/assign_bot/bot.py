from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Set

from aiogram import F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    ReplyKeyboardMarkup,
)

from .selector import ItemSelector, SelectionPolicy


logger = logging.getLogger(__name__)

router = Router(name="assign_bot")


# Список участников по умолчанию, если пользователь ещё не задал свой
DEFAULT_USERNAMES: List[str] = [
    "@MaksimMukhametov",
    "@jellex",
    "@vSmykovsky",
    "@RomanDobrov",
    "@gergoltz",
]


def _parse_admin_user_ids() -> Set[int]:
    """
    Парсит ID администраторов из переменной окружения ADMIN_USER_ID.

    Поддерживаемые форматы:
    - Один ID: "12345678"
    - Несколько ID через запятую: "12345678,87654321,11111111"
    - Несколько ID через пробелы: "12345678 87654321 11111111"

    Returns:
        Множество ID администраторов
    """
    admin_ids_str = os.getenv("ADMIN_USER_ID", "").strip()

    if not admin_ids_str:
        logger.warning(
            "ADMIN_USER_ID не задан в переменных окружения. Администраторов не будет."
        )
        return set()

    try:
        # Поддерживаем разделители: запятая и пробел
        admin_ids_str = admin_ids_str.replace(",", " ")
        admin_ids = {
            int(id_str.strip()) for id_str in admin_ids_str.split() if id_str.strip()
        }

        logger.info(f"Загружено {len(admin_ids)} администратора(ов) из ADMIN_USER_ID")
        return admin_ids

    except ValueError as e:
        logger.error(
            f"Ошибка парсинга ADMIN_USER_ID: {e}. Проверьте формат в .env файле."
        )
        return set()


def _parse_assign_channel_id() -> Optional[str]:
    """
    Парсит ID канала для отправки назначений из переменной окружения ASSIGN_CHANNEL_ID.

    Поддерживаемые форматы:
    - Числовой ID: "-1001234567890"
    - Username канала: "@mychannel"
    - Username канала без @: "mychannel"

    Returns:
        ID канала или None если не задан
    """
    channel_id = os.getenv("ASSIGN_CHANNEL_ID", "").strip()

    if not channel_id:
        logger.warning(
            "ASSIGN_CHANNEL_ID не задан в переменных окружения. Назначения отправляться не будут."
        )
        return None

    # Если это числовой ID, оставляем как есть
    if channel_id.lstrip("-").isdigit():
        logger.info(f"Загружен числовой ID канала: {channel_id}")
        return channel_id

    # Если username без @, добавляем @
    if not channel_id.startswith("@"):
        channel_id = f"@{channel_id}"

    logger.info(f"Загружен username канала: {channel_id}")
    return channel_id


# ID администраторов, которые могут настраивать участников
# Загружается из переменной окружения ADMIN_USER_ID
ADMIN_USER_IDS: Set[int] = _parse_admin_user_ids()

# ID канала для отправки назначений
# Загружается из переменной окружения ASSIGN_CHANNEL_ID
ASSIGN_CHANNEL_ID: Optional[str] = _parse_assign_channel_id()


@dataclass
class UserConfig:
    usernames: List[str] = field(default_factory=list)
    selector: ItemSelector[str] = field(default_factory=lambda: ItemSelector[str]())


# In-memory state per chat. For production, replace with persistent storage
CHAT_STATE: Dict[int, UserConfig] = {}
EXPECT_CONFIG: Set[int] = set()


@dataclass
class PendingAssign:
    active_selected: Set[str] = field(default_factory=set)
    policy: Optional[SelectionPolicy] = None
    count: Optional[int] = None  # количество участников для назначения (1, 2 или 3)
    description: str = ""
    message_id_with_keyboard: Optional[int] = None
    step: Optional[str] = None  # 'configure' | 'await_count' | 'await_description'


PENDING: Dict[int, PendingAssign] = {}


def _get_chat_state(chat_id: int) -> UserConfig:
    if chat_id not in CHAT_STATE:
        CHAT_STATE[chat_id] = UserConfig()
    return CHAT_STATE[chat_id]


def _is_admin(user_id: int) -> bool:
    """Проверяет, является ли пользователь администратором."""
    return user_id in ADMIN_USER_IDS


def _parse_usernames(raw: str) -> List[str]:
    # Split by whitespace/commas, normalize to start with @ and deduplicate preserving order
    tokens: List[str] = [
        t.strip() for t in raw.replace("\n", " ").replace(",", " ").split() if t.strip()
    ]
    seen: set[str] = set()
    result: List[str] = []
    for token in tokens:
        uname: str = token if token.startswith("@") else f"@{token}"
        if uname not in seen:
            seen.add(uname)
            result.append(uname)
    return result


def _format_user_list(usernames: Sequence[str]) -> str:
    if not usernames:
        return "—"
    return "\n".join(f"• {u}" for u in usernames)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else 0
    is_admin = _is_admin(user_id)

    try:
        commands_text = "Доступные команды:\n"
        if is_admin:
            commands_text += "/configure — задать список участников (@usernames)\n"
        commands_text += "/assign — выбрать активных и выполнить назначение\n"
        commands_text += "/myid — показать ваш User ID"

        await message.answer(
            f"Привет! Я Assign Bot.\n\n{commands_text}",
            reply_markup=_main_menu_keyboard(is_admin=is_admin),
        )
    except TelegramAPIError as exc:
        logger.exception("Не удалось отправить ответ на /start: %s", exc)


@router.message(Command("configure"))
async def cmd_configure(message: Message) -> None:
    # Проверяем права администратора
    user_id = message.from_user.id if message.from_user else 0
    if not _is_admin(user_id):
        try:
            await message.answer("У вас нет прав для настройки участников.")
        except TelegramAPIError:
            pass
        return

    chat_id: int = message.chat.id
    _ = _get_chat_state(chat_id)
    is_admin = _is_admin(user_id)

    try:
        await message.answer(
            "Отправьте список участников через пробел/запятую/перенос строки.\n"
            "Пример: @alice, @bob, @carol",
            reply_markup=_main_menu_keyboard(is_admin=is_admin),
        )
    except TelegramAPIError as exc:
        logger.exception("Ошибка при запросе конфигурации: %s", exc)
        return
    # Следующее текстовое сообщение — конфигурация участников
    EXPECT_CONFIG.add(chat_id)


async def handle_config_input(message: Message) -> None:
    chat_id: int = message.chat.id
    state: UserConfig = _get_chat_state(chat_id)
    user_id = message.from_user.id if message.from_user else 0
    is_admin = _is_admin(user_id)

    usernames: List[str] = _parse_usernames(message.text or "")
    if not usernames:
        try:
            await message.answer(
                "Не удалось распознать ни одного пользователя. Попробуйте ещё раз командой /configure."
            )
        except TelegramAPIError:
            pass
        return
    state.usernames = usernames
    # Обновляем селектор с новой коллекцией участников
    state.selector.set_collection(usernames)
    try:
        await message.answer(
            "Список участников сохранён:\n" + _format_user_list(state.usernames),
            reply_markup=_main_menu_keyboard(is_admin=is_admin),
        )
    except TelegramAPIError as exc:
        logger.exception("Не удалось отправить подтверждение конфигурации: %s", exc)


def _main_menu_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Создаёт клавиатуру главного меню.

    Args:
        is_admin: Если True, показывает кнопку Configure Participants
    """
    buttons = []
    if is_admin:
        buttons.append(
            [
                KeyboardButton(text="Configure Participants"),
                KeyboardButton(text="Assign Participants"),
            ]
        )
    else:
        buttons.append([KeyboardButton(text="Assign Participants")])

    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
    )


def _build_toggle_keyboard(
    all_users: Sequence[str], selected: Set[str]
) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    for username in all_users:
        checked: bool = username in selected
        text: str = ("✅ " if checked else "☑️ ") + username
        rows.append(
            [InlineKeyboardButton(text=text, callback_data=f"toggle::{username}")]
        )
    # control row
    rows.append(
        [
            InlineKeyboardButton(text="Далее ▶️", callback_data="next"),
            InlineKeyboardButton(text="Отмена", callback_data="cancel"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _build_count_keyboard() -> InlineKeyboardMarkup:
    """Создаёт клавиатуру для выбора количества участников для назначения."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1️⃣ участник", callback_data="count::1"),
                InlineKeyboardButton(text="2️⃣ участника", callback_data="count::2"),
                InlineKeyboardButton(text="3️⃣ участника", callback_data="count::3"),
            ]
        ]
    )


@router.callback_query(F.data == "assign_help")
async def assign_help(cb: CallbackQuery) -> None:
    try:
        await cb.message.answer(
            "После команды /assign отправьте список активных участников, которых нужно включить в назначение.\n"
            "Пример: @alice, @bob\n\n"
            "Политика выбора: укажите 'round' или 'random' и описание.\n"
            "Пример: round Еженедельная дежурка по поддержке"
        )
        await cb.answer()
    except TelegramAPIError as exc:
        logger.exception("Ошибка в assign_help: %s", exc)


@router.message(Command("assign"))
async def cmd_assign(message: Message) -> None:
    chat_id: int = message.chat.id
    state: UserConfig = _get_chat_state(chat_id)
    if not state.usernames:
        # Используем дефолтных участников, если список пуст
        state.usernames = DEFAULT_USERNAMES.copy()
        state.selector.set_collection(state.usernames)
        try:
            await message.answer(
                "Список участников не был задан. Использую участников по умолчанию:\n"
                + _format_user_list(state.usernames)
            )
        except TelegramAPIError:
            pass
    pending: PendingAssign = PENDING.setdefault(chat_id, PendingAssign())
    pending.active_selected = set()
    pending.policy = None
    pending.count = None
    pending.description = ""
    pending.step = "configure"
    try:
        sent: Message = await message.answer(
            "Выберите активных участников на этот раунд:",
            reply_markup=_build_toggle_keyboard(
                state.usernames, pending.active_selected
            ),
        )
        pending.message_id_with_keyboard = sent.message_id
    except TelegramAPIError as exc:
        logger.exception("Ошибка при старте выбора активных: %s", exc)
        return


@router.callback_query(
    F.data.startswith("toggle::") | (F.data == "next") | (F.data == "cancel")
)
async def handle_toggle(cb: CallbackQuery) -> None:
    chat_id: int = cb.message.chat.id if cb.message else cb.from_user.id
    state: UserConfig = _get_chat_state(chat_id)
    pending: PendingAssign = PENDING.setdefault(chat_id, PendingAssign())
    if cb.data == "cancel":
        PENDING.pop(chat_id, None)
        try:
            await cb.message.edit_text("Операция отменена.")
            await cb.answer()
        except TelegramAPIError:
            pass
        return
    if cb.data == "next":
        if not pending.active_selected:
            try:
                await cb.answer("Выберите хотя бы одного участника", show_alert=True)
            except TelegramAPIError:
                pass
            return
        # show policy selection
        pending.step = "policy"
        try:
            await cb.message.edit_text(
                "Выберите политику назначения:",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="Round-Robin", callback_data="policy::round"
                            ),
                            InlineKeyboardButton(
                                text="Random", callback_data="policy::random"
                            ),
                        ]
                    ]
                ),
            )
            await cb.answer()
        except TelegramAPIError as exc:
            logger.exception("Ошибка при выборе политики: %s", exc)
        return

    # toggle::<username>
    _, username = cb.data.split("::", 1)
    if username in pending.active_selected:
        pending.active_selected.remove(username)
    else:
        if username in set(state.usernames):
            pending.active_selected.add(username)
    # refresh markup
    try:
        await cb.message.edit_reply_markup(
            reply_markup=_build_toggle_keyboard(
                state.usernames, pending.active_selected
            )
        )
        await cb.answer()
    except TelegramAPIError as exc:
        logger.exception("Ошибка обновления клавиатуры выбора: %s", exc)


@router.message(F.text == "Configure Participants")
async def menu_configure(message: Message) -> None:
    # Проверяем права администратора (дублируем проверку из cmd_configure для безопасности)
    user_id = message.from_user.id if message.from_user else 0
    if not _is_admin(user_id):
        try:
            await message.answer("У вас нет прав для настройки участников.")
        except TelegramAPIError:
            pass
        return
    await cmd_configure(message)


@router.message(F.text == "Assign Participants")
async def menu_assign(message: Message) -> None:
    await cmd_assign(message)


@router.message(Command("myid"))
async def cmd_myid(message: Message) -> None:
    """Показывает User ID пользователя для настройки админов."""
    user_id = message.from_user.id if message.from_user else 0
    username = message.from_user.username if message.from_user else "неизвестно"
    is_admin = _is_admin(user_id)

    admin_status = "✅ Администратор" if is_admin else "❌ Обычный пользователь"

    try:
        await message.answer(
            f"Ваш User ID: `{user_id}`\n"
            f"Username: @{username}\n"
            f"Статус: {admin_status}\n\n"
            f"Для добавления в админы добавьте ID в переменную окружения ADMIN_USER_ID в .env файле.",
            parse_mode="Markdown",
        )
    except TelegramAPIError as exc:
        logger.exception("Ошибка при отправке ID: %s", exc)


@router.callback_query(F.data.startswith("policy::"))
async def handle_policy(cb: CallbackQuery) -> None:
    chat_id: int = cb.message.chat.id
    pending: PendingAssign = PENDING.setdefault(chat_id, PendingAssign())
    policy_key: str = cb.data.split("::", 1)[1]
    if policy_key == "round":
        pending.policy = SelectionPolicy.ROUND_ROBIN
    elif policy_key == "random":
        pending.policy = SelectionPolicy.RANDOM
    else:
        try:
            await cb.answer("Неизвестная политика", show_alert=True)
        except TelegramAPIError:
            pass
        return
    pending.step = "await_count"
    try:
        await cb.message.edit_text(
            "Выберите количество участников для назначения:",
            reply_markup=_build_count_keyboard(),
        )
        await cb.answer()
    except TelegramAPIError as exc:
        logger.exception("Ошибка на шаге выбора количества: %s", exc)
        return
    # Следующий callback — выбор количества участников


@router.callback_query(F.data.startswith("count::"))
async def handle_count(cb: CallbackQuery) -> None:
    """Обрабатывает выбор количества участников для назначения."""
    chat_id: int = cb.message.chat.id
    pending: PendingAssign = PENDING.setdefault(chat_id, PendingAssign())

    count_str: str = cb.data.split("::", 1)[1]
    try:
        count = int(count_str)
        if count not in [1, 2, 3]:
            raise ValueError("Invalid count")
        pending.count = count
    except ValueError:
        try:
            await cb.answer("Неизвестное количество участников", show_alert=True)
        except TelegramAPIError:
            pass
        return

    pending.step = "await_description"
    try:
        await cb.message.edit_text("Введите описание задачи (произвольный текст)")
        await cb.answer()
    except TelegramAPIError as exc:
        logger.exception("Ошибка на шаге описания: %s", exc)
        return


async def handle_description_input(message: Message) -> None:
    chat_id: int = message.chat.id
    state: UserConfig = _get_chat_state(chat_id)
    pending: PendingAssign = PENDING.setdefault(chat_id, PendingAssign())
    user_id = message.from_user.id if message.from_user else 0
    is_admin = _is_admin(user_id)

    pending.description = message.text or ""

    # Проверяем что канал сконфигурирован
    if not ASSIGN_CHANNEL_ID:
        try:
            await message.answer(
                "❌ Канал для назначений не сконфигурирован.\n"
                "Обратитесь к администратору для настройки ASSIGN_CHANNEL_ID.",
                reply_markup=_main_menu_keyboard(is_admin=is_admin),
            )
        except TelegramAPIError:
            pass
        # Очищаем состояние
        PENDING.pop(chat_id, None)
        return

    # Выбираем участников и отправляем назначение
    assignees: List[str] = _select_assignees(
        pending.policy or SelectionPolicy.ROUND_ROBIN,
        list(pending.active_selected),
        state,
        pending.count or 1,  # Используем выбранное количество или 1 по умолчанию
    )
    await _post_assignment(
        message, assignees, pending.description, target_chat=ASSIGN_CHANNEL_ID
    )

    # Очищаем состояние
    PENDING.pop(chat_id, None)


@router.message(F.text)
async def handle_text_steps(message: Message) -> None:
    """Единая точка обработки последовательных текстовых шагов.

    - Ожидание конфигурации участников после /configure
    - Ожидание описания после выбора политики
    """
    chat_id: int = message.chat.id
    # текст используется в хендлерах ниже по шагам

    # 1) Конфигурация участников
    if chat_id in EXPECT_CONFIG:
        # Выполнить конфигурацию и очистить флаг ожидания
        await handle_config_input(message)
        EXPECT_CONFIG.discard(chat_id)
        return

    # 2) Шаги назначения
    pending: Optional[PendingAssign] = PENDING.get(chat_id)
    if not pending:
        return
    if pending.step == "await_description":
        await handle_description_input(message)
        return


def _select_assignees(
    policy: SelectionPolicy, active: Sequence[str], state: UserConfig, count: int
) -> List[str]:
    """
    Выбирает участников для назначения используя ItemSelector.

    Args:
        policy: Политика выбора
        active: Список активных участников (подмножество от state.usernames)
        state: Конфигурация пользователя с селектором
        count: Количество участников для выбора (1, 2 или 3)

    Returns:
        Список выбранных участников
    """
    if not active:
        return []

    # Проверяем, что count не превышает количество активных участников
    actual_count = min(count, len(active))

    # Устанавливаем политику и выбираем из активных участников
    state.selector.set_policy(policy)

    try:
        selected = state.selector.select_from_available(active, actual_count)
        return selected
    except ValueError:
        # Если возникла ошибка (например, active содержит элементы не из коллекции),
        # фильтруем active только до валидных пользователей и пробуем снова
        valid_active = [user for user in active if user in state.usernames]
        if not valid_active:
            return []
        state.selector.set_collection(state.usernames)
        actual_count = min(count, len(valid_active))
        selected = state.selector.select_from_available(valid_active, actual_count)
        return selected


async def _post_assignment(
    message: Message,
    assignees: Sequence[str],
    description: str,
    target_chat: Optional[str] = None,
) -> None:
    """
    Отправляет сообщение о назначении с @mentions и poll для отметки выполнения.

    Args:
        message: Исходное сообщение
        assignees: Список назначенных пользователей
        description: Описание задачи
        target_chat: Целевой чат/канал. Если None, отправляется в текущий чат
    """
    if not assignees:
        try:
            await message.answer("Некого назначать — список пуст.")
        except TelegramAPIError:
            pass
        return

    # Определяем куда отправлять и настройки анонимности
    is_channel = target_chat is not None
    chat_id = target_chat if is_channel else message.chat.id
    is_anonymous = is_channel  # Каналы требуют анонимные опросы

    # Формируем текстовое сообщение с @mentions для уведомлений
    assignees_text: str = ", ".join(assignees)
    text: str = f"Назначены: {assignees_text}\n{description}".strip()

    # Отправляем текстовое сообщение с @mentions
    try:
        if is_channel:
            sent: Message = await message.bot.send_message(chat_id=chat_id, text=text)
        else:
            sent: Message = await message.answer(text)
    except TelegramAPIError as exc:
        if is_channel:
            logger.exception(
                "Не удалось отправить сообщение в канал %s: %s", chat_id, exc
            )
            try:
                await message.answer(
                    "Не удалось отправить в канал. Проверьте права бота и имя канала."
                )
            except TelegramAPIError:
                pass
        else:
            logger.exception("Ошибка при отправке сообщения о назначении: %s", exc)
        return

    # Создаем poll для отметки выполнения
    try:
        # Create poll options with assigned users' names
        poll_options = [f"✔️ {assignee}" for assignee in assignees]

        await message.bot.send_poll(
            chat_id=chat_id,
            question="Отметьте выполнение:",
            options=poll_options,
            is_anonymous=is_anonymous,
            allows_multiple_answers=True,
            reply_to_message_id=sent.message_id,  # Связываем poll с текстовым сообщением
        )
    except TelegramAPIError as exc:
        error_context = "в канале" if is_channel else ""
        logger.exception("Не удалось создать опрос %s: %s", error_context, exc)
