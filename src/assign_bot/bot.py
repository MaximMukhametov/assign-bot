from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
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


class Policy(str, Enum):
    ROUND_ROBIN = "round_robin"
    RANDOM = "random"


@dataclass
class UserConfig:
    usernames: List[str] = field(default_factory=list)
    last_assigned_index: int = -1


# In-memory state per chat. For production, replace with persistent storage
CHAT_STATE: Dict[int, UserConfig] = {}
EXPECT_CONFIG: Set[int] = set()


@dataclass
class PendingAssign:
    active_selected: Set[str] = field(default_factory=set)
    policy: Optional[Policy] = None
    description: str = ""
    target_channel: Optional[str] = None
    message_id_with_keyboard: Optional[int] = None
    step: Optional[str] = None  # 'configure' | 'await_description' | 'await_channel'


PENDING: Dict[int, PendingAssign] = {}


def _get_chat_state(chat_id: int) -> UserConfig:
    if chat_id not in CHAT_STATE:
        CHAT_STATE[chat_id] = UserConfig()
    return CHAT_STATE[chat_id]


def _parse_usernames(raw: str) -> List[str]:
    # Split by whitespace/commas, normalize to start with @ and deduplicate preserving order
    tokens: List[str] = [t.strip() for t in raw.replace("\n", " ").replace(",", " ").split() if t.strip()]
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
    try:
        await message.answer(
            "Привет! Я Assign Bot.\n\n"
            "Доступные команды:\n"
            "/configure — задать список участников (@usernames)\n"
            "/assign — выбрать активных и выполнить назначение",
            reply_markup=_main_menu_keyboard(),
        )
    except TelegramAPIError as exc:
        logger.exception("Не удалось отправить ответ на /start: %s", exc)


@router.message(Command("configure"))
async def cmd_configure(message: Message) -> None:
    chat_id: int = message.chat.id
    _ = _get_chat_state(chat_id)
    try:
        await message.answer(
            "Отправьте список участников через пробел/запятую/перенос строки.\n"
            "Пример: @alice, @bob, @carol",
            reply_markup=_main_menu_keyboard(),
        )
    except TelegramAPIError as exc:
        logger.exception("Ошибка при запросе конфигурации: %s", exc)
        return
    # Следующее текстовое сообщение — конфигурация участников
    EXPECT_CONFIG.add(chat_id)


async def handle_config_input(message: Message) -> None:
    chat_id: int = message.chat.id
    state: UserConfig = _get_chat_state(chat_id)
    usernames: List[str] = _parse_usernames(message.text or "")
    if not usernames:
        try:
            await message.answer("Не удалось распознать ни одного пользователя. Попробуйте ещё раз командой /configure.")
        except TelegramAPIError:
            pass
        return
    state.usernames = usernames
    state.last_assigned_index = -1
    try:
        await message.answer(
            "Список участников сохранён:\n" + _format_user_list(state.usernames),
            reply_markup=_main_menu_keyboard(),
        )
    except TelegramAPIError as exc:
        logger.exception("Не удалось отправить подтверждение конфигурации: %s", exc)


def _main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Configure Participants"), KeyboardButton(text="Assign Participants")]
        ],
        resize_keyboard=True,
    )


def _build_toggle_keyboard(all_users: Sequence[str], selected: Set[str]) -> InlineKeyboardMarkup:
    rows: List[List[InlineKeyboardButton]] = []
    for username in all_users:
        checked: bool = username in selected
        text: str = ("✅ " if checked else "☑️ ") + username
        rows.append([InlineKeyboardButton(text=text, callback_data=f"toggle::{username}")])
    # control row
    rows.append(
        [
            InlineKeyboardButton(text="Далее ▶️", callback_data="next"),
            InlineKeyboardButton(text="Отмена", callback_data="cancel"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


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
        state.last_assigned_index = -1
        try:
            await message.answer(
                "Список участников не был задан. Использую участников по умолчанию:\n" +
                _format_user_list(state.usernames)
            )
        except TelegramAPIError:
            pass
    pending: PendingAssign = PENDING.setdefault(chat_id, PendingAssign())
    pending.active_selected = set()
    pending.policy = None
    pending.description = ""
    pending.target_channel = None
    pending.step = 'configure'
    try:
        sent: Message = await message.answer(
            "Выберите активных участников на этот раунд:",
            reply_markup=_build_toggle_keyboard(state.usernames, pending.active_selected),
        )
        pending.message_id_with_keyboard = sent.message_id
    except TelegramAPIError as exc:
        logger.exception("Ошибка при старте выбора активных: %s", exc)
        return


@router.callback_query(F.data.startswith("toggle::") | (F.data == "next") | (F.data == "cancel"))
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
        pending.step = 'policy'
        try:
            await cb.message.edit_text(
                "Выберите политику назначения:",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(text="Round-Robin", callback_data="policy::round"),
                            InlineKeyboardButton(text="Random", callback_data="policy::random"),
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
        await cb.message.edit_reply_markup(reply_markup=_build_toggle_keyboard(state.usernames, pending.active_selected))
        await cb.answer()
    except TelegramAPIError as exc:
        logger.exception("Ошибка обновления клавиатуры выбора: %s", exc)


@router.message(F.text == "Configure Participants")
async def menu_configure(message: Message) -> None:
    await cmd_configure(message)


@router.message(F.text == "Assign Participants")
async def menu_assign(message: Message) -> None:
    await cmd_assign(message)


@router.callback_query(F.data.startswith("policy::"))
async def handle_policy(cb: CallbackQuery) -> None:
    chat_id: int = cb.message.chat.id
    pending: PendingAssign = PENDING.setdefault(chat_id, PendingAssign())
    policy_key: str = cb.data.split("::", 1)[1]
    if policy_key == "round":
        pending.policy = Policy.ROUND_ROBIN
    elif policy_key == "random":
        pending.policy = Policy.RANDOM
    else:
        try:
            await cb.answer("Неизвестная политика", show_alert=True)
        except TelegramAPIError:
            pass
        return
    pending.step = 'await_description'
    try:
        await cb.message.edit_text("Введите описание задачи (произвольный текст)")
        await cb.answer()
    except TelegramAPIError as exc:
        logger.exception("Ошибка на шаге описания: %s", exc)
        return
    # Следующее текстовое сообщение — описание (обрабатывается в общем текстовом обработчике)


async def handle_description_input(message: Message) -> None:
    chat_id: int = message.chat.id
    pending: PendingAssign = PENDING.setdefault(chat_id, PendingAssign())
    pending.description = message.text or ""
    pending.step = 'await_channel'
    try:
        await message.answer(
            "Укажите целевой канал (как @channel_username), куда отправить назначение",
            reply_markup=_main_menu_keyboard(),
        )
    except TelegramAPIError:
        pass
    # Следующее текстовое сообщение — канал (обрабатывается в общем текстовом обработчике)


async def handle_channel_input(message: Message) -> None:
    chat_id: int = message.chat.id
    state: UserConfig = _get_chat_state(chat_id)
    pending: PendingAssign = PENDING.setdefault(chat_id, PendingAssign())
    raw: str = (message.text or "").strip()
    if not raw.startswith("@"):
        try:
            await message.answer("Ожидается имя канала в виде @channel_username. Попробуйте ещё раз.")
        except TelegramAPIError:
            pass
        return
    pending.target_channel = raw
    # compute assignees and post
    assignees: List[str] = _select_assignees(pending.policy or Policy.ROUND_ROBIN, list(pending.active_selected), state)
    await _post_assignment_to_channel(message, assignees, pending.description, pending.target_channel)
    # cleanup
    PENDING.pop(chat_id, None)


@router.message(F.text)
async def handle_text_steps(message: Message) -> None:
    """Единая точка обработки последовательных текстовых шагов.

    - Ожидание конфигурации участников после /configure
    - Ожидание описания после выбора политики
    - Ожидание канала после ввода описания
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
    if pending.step == 'await_description':
        await handle_description_input(message)
        return
    if pending.step == 'await_channel':
        await handle_channel_input(message)
        return


def _select_assignees(policy: Policy, active: Sequence[str], state: UserConfig) -> List[str]:
    import random

    if policy is Policy.RANDOM:
        # pick 1-2 assignees depending on team size for demonstration
        k: int = 2 if len(active) >= 2 else 1
        return random.sample(list(active), k=k)

    # round-robin: move pointer and pick next
    if not active:
        return []

    # Ensure last_assigned_index aligns with active set by mapping to indices of full list
    # Simplified approach: pick next from active based on state pointer cycling over saved list order
    saved: List[str] = state.usernames
    if not saved:
        return list(active[:1])

    # Find the next saved username that is in active
    idx: int = state.last_assigned_index
    for _ in range(len(saved)):
        idx = (idx + 1) % len(saved)
        candidate: str = saved[idx]
        if candidate in active:
            state.last_assigned_index = idx
            return [candidate]

    # Fallback
    return [active[0]]


async def _post_assignment(message: Message, assignees: Sequence[str], description: str) -> None:
    if not assignees:
        try:
            await message.answer("Некого назначать — список пуст.")
        except TelegramAPIError:
            pass
        return

    assignees_text: str = ", ".join(assignees)
    text: str = f"Назначены: {assignees_text}\n{description}".strip()
    try:
        sent: Message = await message.answer(text)
    except TelegramAPIError as exc:
        logger.exception("Ошибка при отправке сообщения о назначении: %s", exc)
        return

    # Create a poll with checkboxes to mark completion
    try:
        await message.bot.send_poll(
            chat_id=message.chat.id,
            question="Отметьте выполнение",
            options=["✔️ Done"],
            is_anonymous=False,
            allows_multiple_answers=True,
            reply_to_message_id=sent.message_id,
        )
    except TelegramAPIError as exc:
        logger.exception("Не удалось создать опрос: %s", exc)


async def _post_assignment_to_channel(message: Message, assignees: Sequence[str], description: str, channel: str) -> None:
    if not assignees:
        try:
            await message.answer("Некого назначать — список пуст.")
        except TelegramAPIError:
            pass
        return
    assignees_text: str = ", ".join(assignees)
    text: str = f"Назначены: {assignees_text}\n{description}".strip()
    try:
        sent: Message = await message.bot.send_message(chat_id=channel, text=text)
    except TelegramAPIError as exc:
        logger.exception("Не удалось отправить сообщение в канал %s: %s", channel, exc)
        try:
            await message.answer("Не удалось отправить в канал. Проверьте права бота и имя канала.")
        except TelegramAPIError:
            pass
        return
    try:
        await message.bot.send_poll(
            chat_id=channel,
            question="Отметьте выполнение",
            options=["✔️ Done"],
            is_anonymous=False,
            allows_multiple_answers=True,
            reply_to_message_id=sent.message_id,
        )
    except TelegramAPIError as exc:
        logger.exception("Не удалось создать опрос в канале: %s", exc)


