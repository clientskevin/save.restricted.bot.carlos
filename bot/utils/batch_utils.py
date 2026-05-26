import asyncio
import logging
import random
from datetime import datetime
from pyrogram import Client
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from bot.config import Config
from bot.enums import TransferStatus
from bot.utils import get_link_parts, get_user_client, get_media_type, forward_message, is_input_cancelled
from database import db

logger = logging.getLogger(__name__)

RUNNING_TASKS = set()


def format_task_text(task: dict) -> str:
    """Format the task status into human readable text"""
    scanned_count = (task["current_message_id"] - task["first_message_id"] + 1) if task["status"] != "completed" else task["total_messages"]
    scanned_count = max(0, min(scanned_count, task["total_messages"]))
    pct = (scanned_count / task["total_messages"]) * 100 if task["total_messages"] > 0 else 0
    left_count = max(0, task["total_messages"] - scanned_count)
    chat_id = task["source_chat_id"]
    chat_title = task.get("source_chat_title", "Chat")
    chat_id_raw = str(chat_id).replace("-100", "")
    msg_id = task["current_message_id"]
    msg_link = f"https://t.me/c/{chat_id_raw}/{msg_id}"
    last_msg_id = task["last_message_id"]
    last_msg_link = f"https://t.me/c/{chat_id_raw}/{last_msg_id}"

    started_at, running_since = format_time_and_duration(task.get("created_at"))

    status_emoji = {
        "running": "⚡ RUNNING",
        "completed": "✅ COMPLETED",
        "paused": "⏸️ PAUSED",
        "stopped": "⏹️ STOPPED",
        "failed": "❌ FAILED"
    }.get(task["status"].lower(), task["status"].upper())

    notion_tag = " (🌐 Notion)" if task.get("notion_enabled", False) else ""

    text = (
        f"📦 **Task #{task['_id']}** | {status_emoji}{notion_tag}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"**Chat**: {chat_title}\n"
        f"**Progress**: `{scanned_count}`/`{task['total_messages']}` (`{pct:.1f}%` - `{left_count}` left)\n"
        f"**Saved**: `{task['processed_count']}` messages\n"
        f"**Started**: {started_at} ({running_since})\n"
        f"**Links**: [Current]({msg_link}) | [Last]({last_msg_link})\n\n"
        f"ℹ️ __Empty, deleted, or unsupported messages in the range are skipped.__"
    )
    return text


def format_time_and_duration(created_at) -> tuple[str, str]:
    """Format datetime to a human readable relative duration with condensed timezone and date"""
    if not created_at:
        return "Unknown", "N/A"
    
    if isinstance(created_at, str):
        try:
            created_at = datetime.fromisoformat(created_at)
        except Exception:
            return str(created_at), "N/A"
            
    if created_at.tzinfo is None:
        created_at = created_at.astimezone()
        
    raw_tz = created_at.strftime("%Z")
    if not raw_tz:
        tz_offset = created_at.strftime("%z")
        if len(tz_offset) == 5:
            raw_tz = f"{tz_offset[:3]}:{tz_offset[3:]}"
        else:
            raw_tz = tz_offset

    tz_name = abbreviate_timezone(raw_tz)

    started_str = created_at.strftime("%d %b %y, %H:%M")
    if tz_name:
        started_str += f" {tz_name}"
    
    now = datetime.now().astimezone()
    diff = now - created_at
    diff_sec = int(diff.total_seconds())
    
    if diff_sec < 60:
        return started_str, "just now"
    if diff_sec < 3600:
        minutes = diff_sec // 60
        return started_str, f"{minutes}m ago"
    if diff_sec < 86400:
        hours = diff_sec // 3600
        minutes = (diff_sec % 3600) // 60
        return started_str, f"{hours}h {minutes}m ago"
        
    days = diff_sec // 86400
    hours = (diff_sec % 86400) // 3600
    return started_str, f"{days}d {hours}h ago"


def abbreviate_timezone(tz_name: str) -> str:
    """Condense long timezone names (e.g. India Standard Time -> IST)"""
    if not tz_name:
        return ""
    
    mappings = {
        "india standard time": "IST",
        "coordinated universal time": "UTC",
        "greenwich mean time": "GMT",
        "eastern standard time": "EST",
        "eastern daylight time": "EDT",
        "central standard time": "CST",
        "central daylight time": "CDT",
        "mountain standard time": "MST",
        "mountain daylight time": "MDT",
        "pacific standard time": "PST",
        "pacific daylight time": "PDT"
    }
    mapped = mappings.get(tz_name.lower())
    if mapped:
        return mapped
        
    if len(tz_name) <= 5 and tz_name.isupper():
        return tz_name
        
    abbrev = "".join([char for char in tz_name if char.isupper()])
    return abbrev if abbrev else tz_name


def make_task_markup(task: dict) -> InlineKeyboardMarkup:
    """Generate control buttons based on task status"""
    buttons = []
    if task["status"] == "running":
        buttons.append(InlineKeyboardButton("⏸️ Pause", callback_data=f"b_pause_{task['_id']}"))
        buttons.append(InlineKeyboardButton("⏹️ Stop/Cancel", callback_data=f"b_cancel_{task['_id']}"))
    elif task["status"] in ["paused", "failed"]:
        buttons.append(InlineKeyboardButton("▶️ Resume", callback_data=f"b_resume_{task['_id']}"))
        buttons.append(InlineKeyboardButton("❌ Delete", callback_data=f"b_delete_{task['_id']}"))
    else:
        buttons.append(InlineKeyboardButton("❌ Delete", callback_data=f"b_delete_{task['_id']}"))
        
    notion = task.get("notion_enabled", False)
    layout = [
        buttons,
        [InlineKeyboardButton("🔄 Refresh", callback_data=f"b_refresh_{task['_id']}")],
        [InlineKeyboardButton("🔙 Back to Menu", callback_data=f"bmenu_home_{notion}")]
    ]
    
    return InlineKeyboardMarkup(layout)


async def resolve_chat_id(bot: Client, user_id: int, text: str) -> int:
    """Helper to resolve a username, ID, or message link to a chat ID"""
    parts = get_link_parts(text)
    if parts:
        return parts[0]
    if text.startswith("-100") and text[4:].isdigit():
        return int(text)
    if text.isdigit():
        return int(text)
    username = text.replace("@", "").strip()
    try:
        app = await get_user_client(user_id)
        chat = await app.get_chat(username)
        return chat.id
    except Exception as e:
        await bot.send_message(user_id, f"❌ Chat not found: {e}")
        return 0


async def create_and_run_task(bot: Client, user_id: int, chat_id: int, start_id: int, end_id: int, notion: bool, title: str = "Chat"):
    """Creates the batch task in DB and starts it in the background"""
    active = await db.batch_tasks.get_active_task(user_id)
    if active:
        return await bot.send_message(user_id, "⚠️ You already have a running batch task. Pause it first.")

    task_id = random.randint(100000, 999999)
    doc = {
        "task_id": task_id,
        "user_id": user_id,
        "source_chat_id": chat_id,
        "source_chat_title": title,
        "first_message_id": start_id,
        "last_message_id": end_id,
        "total_messages": end_id - start_id + 1,
        "notion_enabled": notion
    }
    await db.batch_tasks.create_task(doc)
    await start_background_batch(bot, user_id, task_id)

    task = await db.batch_tasks.read(task_id)
    if task:
        await bot.send_message(user_id, format_task_text(task), reply_markup=make_task_markup(task))


async def setup_custom_task(bot: Client, user_id: int, first_parts: tuple, last_text: str, notion: bool):
    """Calculates batch task start and end points and starts task"""
    chat_id, first_id, _ = first_parts
    if last_text.isdigit():
        last_id = first_id + int(last_text) - 1
    else:
        last_parts = get_link_parts(last_text)
        if not last_parts or last_parts[0] != chat_id:
            return await bot.send_message(user_id, "❌ Invalid link or different chat.")
        last_id = last_parts[1]

    if last_id < first_id:
        return await bot.send_message(user_id, "❌ Last message must be older/higher than first message.")

    app = await get_user_client(user_id)
    chat = await app.get_chat(chat_id) if app else None
    title = chat.title or getattr(chat, "first_name", "Chat") if chat else "Chat"

    await create_and_run_task(bot, user_id, chat_id, first_id, last_id, notion, title)


async def setup_sync_task(bot: Client, user_id: int, chat_id: int, notion: bool, title: str = None):
    """Computes sync range and submits task"""
    app = await get_user_client(user_id)
    if not app:
        return await bot.send_message(user_id, "⚠️ Please log in first.")

    max_indexed = await db.batch_tasks.get_max_message_id(chat_id)
    if max_indexed is None:
        return await bot.send_message(
            user_id,
            "❌ No indexed messages found for this chat. Run a Custom Batch first to initialize."
        )

    latest_id = await get_latest_message_id(app, chat_id)
    if latest_id == 0:
        return await bot.send_message(user_id, "❌ Could not fetch channel history.")

    start_id = max_indexed + 1
    if latest_id < start_id:
        return await bot.send_message(user_id, "✅ Channel is already fully indexed/synced!")

    if not title:
        try:
            chat = await app.get_chat(chat_id) if app else None
            title = chat.title or getattr(chat, "first_name", "Chat") if chat else "Chat"
        except Exception:
            title = "Chat"

    await bot.send_message(user_id, f"ℹ️ Syncing from message ID {start_id} to {latest_id}.")
    await create_and_run_task(bot, user_id, chat_id, start_id, latest_id, notion, title)


async def get_latest_message_id(app: Client, chat_id: int) -> int:
    """Retrieve the newest message ID from the source chat"""
    try:
        async for msg in app.get_chat_history(chat_id, limit=1):
            return msg.id
    except Exception as e:
        logger.error(f"Error fetching latest message ID: {e}")
    return 0


async def start_background_batch(bot: Client, user_id: int, task_id: int):
    """Launch the async processing loop in the background"""
    if task_id in RUNNING_TASKS:
        return
    RUNNING_TASKS.add(task_id)
    asyncio.create_task(process_batch_task(bot, user_id, task_id))


async def load_task_context(task_id: int, user_id: int):
    """Retrieve Pyrogram client and DB task context"""
    app = await get_user_client(user_id)
    if not app:
        await db.batch_tasks.update_status(task_id, "failed")
        return None, None
    task = await db.batch_tasks.read(task_id)
    return app, task


async def process_batch_task(bot: Client, user_id: int, task_id: int):
    """Background task main entrypoint"""
    app, task = await load_task_context(task_id, user_id)
    if not app or not task:
        return
    try:
        processed_count = await run_batch_loop(bot, app, task, task_id, user_id)
        await complete_or_pause_task(bot, task_id, user_id, processed_count)
    except Exception as e:
        logger.error(f"Error in task {task_id}: {e}")
        await db.batch_tasks.update_status(task_id, "failed")
    finally:
        RUNNING_TASKS.discard(task_id)


async def check_task_active(task_id: int) -> bool:
    """Check if task is still running in database"""
    task = await db.batch_tasks.read(task_id)
    return task is not None and task.get("status") == "running"


async def run_batch_loop(bot: Client, app: Client, task: dict, task_id: int, user_id: int) -> int:
    """Execute message range loop updating progress"""
    start_id = task["current_message_id"]
    end_id = task["last_message_id"]
    chat_id = task["source_chat_id"]
    notion = task.get("notion_enabled", False)
    count = task.get("processed_count", 0)

    for msg_id in range(start_id, end_id + 1):
        if not await check_task_active(task_id):
            break
        await db.batch_tasks.update_progress(task_id, msg_id, count)
        success = await process_message_item(bot, app, chat_id, msg_id, user_id, notion)
        count += 1 if success else 0
        await asyncio.sleep(Config.SLEEP_TIME)
    return count


async def complete_or_pause_task(bot: Client, task_id: int, user_id: int, processed_count: int):
    """Handle batch finalization and update status"""
    task = await db.batch_tasks.read(task_id)
    if not task or task.get("status") != "running":
        return
    if task["current_message_id"] >= task["last_message_id"]:
        await db.batch_tasks.update_status(task_id, "completed", processed_count)
        await bot.send_message(user_id, f"✅ Batch task #{task_id} completed. Processed {processed_count} messages.")
    else:
        await db.batch_tasks.update_status(task_id, "paused", processed_count)


async def process_message_item(
    bot: Client, app: Client, chat_id: int, message_id: int, user_id: int, notion_enabled: bool
) -> bool:
    """Fetch and forward a single message, handling media limitations"""
    try:
        message = await app.get_messages(chat_id, message_id)
    except Exception as e:
        logger.debug(f"Could not get message {message_id}: {e}")
        return False

    if not message or message.empty or message.sticker or message.service:
        return False

    allowed_media = await get_media_type()
    if message.media and message.media.value not in allowed_media:
        return False
    if message.text and "text" not in allowed_media:
        return False

    download_id = random.randint(100000, 999999)
    message.download_id = download_id
    message.index = f"{message_id}"

    Config.TRANSFERS[download_id] = {
        "user_id": user_id,
        "status": TransferStatus.IN_PROGRESS.value,
    }

    try:
        await forward_message(bot, app, message, user_id, notion_enabled=notion_enabled)
        return True
    finally:
        Config.TRANSFERS.pop(download_id, None)


async def show_active_task(bot: Client, chat_id: int, user_id: int, query = None):
    """Fetch and display the currently active running batch task"""
    task = await db.batch_tasks.get_active_task(user_id)
    if not task:
        text = "⚠️ No active task currently running."
        markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back to Menu", callback_data="bmenu_home_False")]])
        if query:
            await query.message.edit_text(text, reply_markup=markup)
        else:
            await bot.send_message(chat_id, text, reply_markup=markup)
        return

    text = format_task_text(task)
    markup = make_task_markup(task)
    if query:
        await query.message.edit_text(text, reply_markup=markup)
    else:
        await bot.send_message(chat_id, text, reply_markup=markup)


async def show_completed_tasks(bot: Client, chat_id: int, user_id: int, query = None):
    """Fetch and display the condensed list of completed/inactive tasks"""
    tasks = await db.batch_tasks.get_user_tasks(user_id)
    completed_tasks = [t for t in tasks if t["status"] != "running"]
    text = get_condensed_completed_text(tasks)
    
    # Generate buttons for each task to view details
    buttons = []
    current_row = []
    for task in completed_tasks[:10]:
        task_id = task["_id"]
        current_row.append(InlineKeyboardButton(f"#{task_id}", callback_data=f"b_view_{task_id}"))
        if len(current_row) == 3:
            buttons.append(current_row)
            current_row = []
    if current_row:
        buttons.append(current_row)
        
    buttons.append([InlineKeyboardButton("🔙 Back to Menu", callback_data="bmenu_home_False")])
    markup = InlineKeyboardMarkup(buttons)
    
    if query:
        await query.message.edit_text(text, reply_markup=markup)
    else:
        await bot.send_message(chat_id, text, reply_markup=markup)


def get_condensed_completed_text(tasks: list) -> str:
    """Generate condensed text for completed/inactive tasks"""
    text = "📜 **Completed & Inactive Tasks**\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
    completed_tasks = [t for t in tasks if t["status"] != "running"]
    
    if not completed_tasks:
        text += "No completed or inactive tasks found."
        return text
        
    for task in completed_tasks[:10]:  # Show top 10 completed/inactive tasks
        title = task.get("source_chat_title", "Chat")
        scanned = task.get("total_messages", 0)
        saved = task.get("processed_count", 0)
        
        status_tag = {
            "completed": "✅ COMPLETED",
            "paused": "⏸️ PAUSED",
            "stopped": "⏹️ STOPPED",
            "failed": "❌ FAILED"
        }.get(task["status"].lower(), task["status"].upper())
        
        started_at = "Unknown"
        if task.get("created_at"):
            created_at = task["created_at"]
            if isinstance(created_at, str):
                try:
                    created_at = datetime.fromisoformat(created_at)
                except Exception:
                    pass
            if not isinstance(created_at, str):
                started_at = created_at.strftime("%d-%m-%Y %H:%M")
                
        text += (
            f"• **Task #{task['_id']}** | {status_tag}\n"
            f"  **Chat**: {title}\n"
            f"  Progress: `{scanned}/{scanned}` | Saved: `{saved}` | `{started_at}`\n\n"
        )
    return text.strip()
