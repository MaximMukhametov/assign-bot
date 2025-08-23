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


# Default participants list if user hasn't set their own yet
DEFAULT_USERNAMES: List[str] = [
    "@MaksimMukhametov",
    "@jellex",
    "@vSmykovsky",
    "@RomanDobrov",
    "@gergoltz",
]


def _parse_admin_user_ids() -> Set[int]:
    """
    Parses admin IDs from ADMIN_USER_ID environment variable.

    Supported formats:
    - Single ID: "12345678"
    - Multiple IDs with commas: "12345678,87654321,11111111"
    - Multiple IDs with spaces: "12345678 87654321 11111111"

    Returns:
        Set of admin IDs
    """
    admin_ids_str = os.getenv("ADMIN_USER_ID", "").strip()

    if not admin_ids_str:
        logger.warning(
            "ADMIN_USER_ID not set in environment variables. No administrators will be configured."
        )
        return set()

    try:
        # Support delimiters: comma and space
        admin_ids_str = admin_ids_str.replace(",", " ")
        admin_ids = {
            int(id_str.strip()) for id_str in admin_ids_str.split() if id_str.strip()
        }

        logger.info(f"Loaded {len(admin_ids)} administrator(s) from ADMIN_USER_ID")
        return admin_ids

    except ValueError as e:
        logger.error(
            f"Error parsing ADMIN_USER_ID: {e}. Check the format in .env file."
        )
        return set()


def _parse_assign_channel_id() -> Optional[str]:
    """
    Parses channel ID for sending assignments from ASSIGN_CHANNEL_ID environment variable.

    Supported formats:
    - Numeric ID: "-1001234567890"
    - Channel username: "@mychannel"
    - Channel username without @: "mychannel"

    Returns:
        Channel ID or None if not set
    """
    channel_id = os.getenv("ASSIGN_CHANNEL_ID", "").strip()

    if not channel_id:
        logger.warning(
            "ASSIGN_CHANNEL_ID not set in environment variables. Assignments will not be sent."
        )
        return None

    # If it's a numeric ID, leave as is
    if channel_id.lstrip("-").isdigit():
        logger.info(f"Loaded numeric channel ID: {channel_id}")
        return channel_id

    # If username without @, add @
    if not channel_id.startswith("@"):
        channel_id = f"@{channel_id}"

    logger.info(f"Loaded channel username: {channel_id}")
    return channel_id


# Admin IDs that can configure participants
# Loaded from ADMIN_USER_ID environment variable
ADMIN_USER_IDS: Set[int] = _parse_admin_user_ids()

# Channel ID for sending assignments
# Loaded from ASSIGN_CHANNEL_ID environment variable
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
    count: Optional[int] = None  # number of participants for assignment (1, 2 or 3)
    description: str = ""
    message_id_with_keyboard: Optional[int] = None
    step: Optional[str] = None  # 'configure' | 'await_count' | 'await_description'


PENDING: Dict[int, PendingAssign] = {}


def _get_chat_state(chat_id: int) -> UserConfig:
    if chat_id not in CHAT_STATE:
        CHAT_STATE[chat_id] = UserConfig()
    return CHAT_STATE[chat_id]


def _is_admin(user_id: int) -> bool:
    """Checks if user is an administrator."""
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
        commands_text = "Available commands:\n"
        if is_admin:
            commands_text += "/configure — set participants list (@usernames)\n"
        commands_text += "/assign — select active participants and perform assignment\n"
        commands_text += "/myid — show your User ID"

        await message.answer(
            f"Hello! I'm Assign Bot.\n\n{commands_text}",
            reply_markup=_main_menu_keyboard(is_admin=is_admin),
        )
    except TelegramAPIError as exc:
        logger.exception("Failed to send reply to /start: %s", exc)


@router.message(Command("configure"))
async def cmd_configure(message: Message) -> None:
    # Check admin rights
    user_id = message.from_user.id if message.from_user else 0
    if not _is_admin(user_id):
        try:
            await message.answer("You don't have permissions to configure participants.")
        except TelegramAPIError:
            pass
        return

    chat_id: int = message.chat.id
    _ = _get_chat_state(chat_id)
    is_admin = _is_admin(user_id)

    try:
        await message.answer(
            "Send participants list separated by space/comma/newline.\n"
            "Example: @alice, @bob, @carol",
            reply_markup=_main_menu_keyboard(is_admin=is_admin),
        )
    except TelegramAPIError as exc:
        logger.exception("Error requesting configuration: %s", exc)
        return
    # Next text message will be participants configuration
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
                "Could not recognize any users. Please try again with /configure command."
            )
        except TelegramAPIError:
            pass
        return
    state.usernames = usernames
    # Update selector with new participants collection
    state.selector.set_collection(usernames)
    try:
        await message.answer(
            "Participants list saved:\n" + _format_user_list(state.usernames),
            reply_markup=_main_menu_keyboard(is_admin=is_admin),
        )
    except TelegramAPIError as exc:
        logger.exception("Failed to send configuration confirmation: %s", exc)


def _main_menu_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Creates main menu keyboard.

    Args:
        is_admin: If True, shows Configure Participants button
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
            InlineKeyboardButton(text="Next ▶️", callback_data="next"),
            InlineKeyboardButton(text="Cancel", callback_data="cancel"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _build_count_keyboard() -> InlineKeyboardMarkup:
    """Creates keyboard for selecting number of participants for assignment."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1️⃣ participant", callback_data="count::1"),
                InlineKeyboardButton(text="2️⃣ participants", callback_data="count::2"),
                InlineKeyboardButton(text="3️⃣ participants", callback_data="count::3"),
            ]
        ]
    )


@router.callback_query(F.data == "assign_help")
async def assign_help(cb: CallbackQuery) -> None:
    try:
        await cb.message.answer(
            "After /assign command send list of active participants to include in assignment.\n"
            "Example: @alice, @bob\n\n"
            "Selection policy: specify 'round' or 'random' and description.\n"
            "Example: round Weekly support duty"
        )
        await cb.answer()
    except TelegramAPIError as exc:
        logger.exception("Error in assign_help: %s", exc)


@router.message(Command("assign"))
async def cmd_assign(message: Message) -> None:
    chat_id: int = message.chat.id
    state: UserConfig = _get_chat_state(chat_id)
    if not state.usernames:
            # Use default participants if list is empty
        state.usernames = DEFAULT_USERNAMES.copy()
        state.selector.set_collection(state.usernames)
        try:
            await message.answer(
                "Participants list was not set. Using default participants:\n"
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
            "Select active participants for this round:",
            reply_markup=_build_toggle_keyboard(
                state.usernames, pending.active_selected
            ),
        )
        pending.message_id_with_keyboard = sent.message_id
    except TelegramAPIError as exc:
        logger.exception("Error starting active selection: %s", exc)
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
            await cb.message.edit_text("Operation cancelled.")
            await cb.answer()
        except TelegramAPIError:
            pass
        return
    if cb.data == "next":
        if not pending.active_selected:
            try:
                await cb.answer("Select at least one participant", show_alert=True)
            except TelegramAPIError:
                pass
            return
        # show policy selection
        pending.step = "policy"
        try:
            await cb.message.edit_text(
                "Select assignment policy:",
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
            logger.exception("Error in policy selection: %s", exc)
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
        logger.exception("Error updating selection keyboard: %s", exc)


@router.message(F.text == "Configure Participants")
async def menu_configure(message: Message) -> None:
    # Check admin rights (duplicate check from cmd_configure for security)
    user_id = message.from_user.id if message.from_user else 0
    if not _is_admin(user_id):
        try:
            await message.answer("You don't have permissions to configure participants.")
        except TelegramAPIError:
            pass
        return
    await cmd_configure(message)


@router.message(F.text == "Assign Participants")
async def menu_assign(message: Message) -> None:
    await cmd_assign(message)


@router.message(Command("myid"))
async def cmd_myid(message: Message) -> None:
    """Shows user's User ID for admin configuration."""
    user_id = message.from_user.id if message.from_user else 0
    username = message.from_user.username if message.from_user else "unknown"
    is_admin = _is_admin(user_id)

    admin_status = "✅ Administrator" if is_admin else "❌ Regular user"

    try:
        await message.answer(
            f"Your User ID: `{user_id}`\n"
            f"Username: @{username}\n"
            f"Status: {admin_status}\n\n"
            f"To add as admin, add ID to ADMIN_USER_ID environment variable in .env file.",
            parse_mode="Markdown",
        )
    except TelegramAPIError as exc:
        logger.exception("Error sending ID: %s", exc)


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
            await cb.answer("Unknown policy", show_alert=True)
        except TelegramAPIError:
            pass
        return
    pending.step = "await_count"
    try:
        await cb.message.edit_text(
            "Select number of participants for assignment:",
            reply_markup=_build_count_keyboard(),
        )
        await cb.answer()
    except TelegramAPIError as exc:
        logger.exception("Error at count selection step: %s", exc)
        return
    # Next callback - selecting number of participants


@router.callback_query(F.data.startswith("count::"))
async def handle_count(cb: CallbackQuery) -> None:
    """Handles selection of number of participants for assignment."""
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
            await cb.answer("Unknown number of participants", show_alert=True)
        except TelegramAPIError:
            pass
        return

    pending.step = "await_description"
    try:
        await cb.message.edit_text("Enter task description (any text)")
        await cb.answer()
    except TelegramAPIError as exc:
        logger.exception("Error at description step: %s", exc)
        return


async def handle_description_input(message: Message) -> None:
    chat_id: int = message.chat.id
    state: UserConfig = _get_chat_state(chat_id)
    pending: PendingAssign = PENDING.setdefault(chat_id, PendingAssign())
    user_id = message.from_user.id if message.from_user else 0
    is_admin = _is_admin(user_id)

    pending.description = message.text or ""

    # Check that channel is configured
    if not ASSIGN_CHANNEL_ID:
        try:
            await message.answer(
                "❌ Assignment channel not configured.\n"
                "Contact administrator to configure ASSIGN_CHANNEL_ID.",
                reply_markup=_main_menu_keyboard(is_admin=is_admin),
            )
        except TelegramAPIError:
            pass
        # Clear state
        PENDING.pop(chat_id, None)
        return

    # Select participants and send assignment
    assignees: List[str] = _select_assignees(
        pending.policy or SelectionPolicy.ROUND_ROBIN,
        list(pending.active_selected),
        state,
        pending.count or 1,  # Use selected count or 1 by default
    )
    await _post_assignment(
        message, assignees, pending.description, target_chat=ASSIGN_CHANNEL_ID
    )

    # Clear state
    PENDING.pop(chat_id, None)


@router.message(F.text)
async def handle_text_steps(message: Message) -> None:
    """Single point for handling sequential text steps.

    - Waiting for participants configuration after /configure
    - Waiting for description after policy selection
    """
    chat_id: int = message.chat.id
    # text is used in handlers below by steps

    # 1) Participants configuration
    if chat_id in EXPECT_CONFIG:
        # Execute configuration and clear waiting flag
        await handle_config_input(message)
        EXPECT_CONFIG.discard(chat_id)
        return

    # 2) Assignment steps
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
    Selects participants for assignment using ItemSelector.

    Args:
        policy: Selection policy
        active: List of active participants (subset of state.usernames)
        state: User configuration with selector
        count: Number of participants to select (1, 2 or 3)

    Returns:
        List of selected participants
    """
    if not active:
        return []

    # Check that count doesn't exceed number of active participants
    actual_count = min(count, len(active))

    # Set policy and select from active participants
    state.selector.set_policy(policy)

    try:
        selected = state.selector.select_from_available(active, actual_count)
        return selected
    except ValueError:
        # If error occurred (e.g., active contains elements not from collection),
        # filter active to only valid users and try again
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
    Sends assignment message with @mentions and poll for completion tracking.

    Args:
        message: Original message
        assignees: List of assigned users
        description: Task description
        target_chat: Target chat/channel. If None, sends to current chat
    """
    if not assignees:
        try:
            await message.answer("No one to assign — list is empty.")
        except TelegramAPIError:
            pass
        return

    # Determine where to send and anonymity settings
    is_channel = target_chat is not None
    chat_id = target_chat if is_channel else message.chat.id
    is_anonymous = is_channel  # Channels require anonymous polls

    # Form text message with @mentions for notifications
    assignees_text: str = ", ".join(assignees)
    text: str = f"Assigned: {assignees_text}\n{description}".strip()

    # Send text message with @mentions
    try:
        if is_channel:
            sent: Message = await message.bot.send_message(chat_id=chat_id, text=text)
        else:
            sent: Message = await message.answer(text)
    except TelegramAPIError as exc:
        if is_channel:
            logger.exception(
                "Failed to send message to channel %s: %s", chat_id, exc
            )
            try:
                await message.answer(
                    "Failed to send to channel. Check bot permissions and channel name."
                )
            except TelegramAPIError:
                pass
        else:
            logger.exception("Error sending assignment message: %s", exc)
        return

    # Create poll for completion tracking
    try:
        # Create poll options with assigned users' names
        poll_options = [f"✔️ {assignee}" for assignee in assignees]

        await message.bot.send_poll(
            chat_id=chat_id,
            question="Mark completion:",
            options=poll_options,
            is_anonymous=is_anonymous,
            allows_multiple_answers=True,
            reply_to_message_id=sent.message_id,  # Link poll to text message
        )
    except TelegramAPIError as exc:
        error_context = "in channel" if is_channel else ""
        logger.exception("Failed to create poll %s: %s", error_context, exc)
