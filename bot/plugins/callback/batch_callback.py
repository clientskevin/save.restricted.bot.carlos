from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from bot.config import Config
from bot.utils import (
    show_active_task,
    show_completed_tasks,
    format_task_text,
    make_task_markup,
    is_input_cancelled,
    get_link_parts,
    setup_custom_task,
    setup_sync_task,
    resolve_chat_id,
    start_background_batch,
    make_batch_menu
)
from database import db


@Client.on_callback_query(filters.regex(r"^bmenu_new_") & filters.user(Config.OWNER_ID))
async def handle_new_batch(bot: Client, query: CallbackQuery):
    """Initiates custom message range batch creation"""
    notion = query.data.split("_")[-1] == "True"
    user_id = query.from_user.id

    first_text = (
        "📊 **New Custom Batch**\n\n"
        "This copies a specific range of messages from a chat.\n\n"
        "Forward/send the **first message link** from the chat you would like to batch-save.\n\n"
        "Example:\n`https://t.me/c/2114152609/1`\n\n"
        "Send `/cancel` to cancel ❌"
    )
    first_ask = await query.message.chat.ask(first_text)
    if await is_input_cancelled(first_ask):
        return

    first_parts = get_link_parts(first_ask.text)
    if not first_parts:
        return await bot.send_message(user_id, f"❌ Invalid link: {first_ask.text}")

    last_text = (
        "📊 **New Custom Batch**\n\n"
        "Now, choose how far the copy task should go.\n\n"
        "Please send one of the following:\n\n"
        "1️⃣ **The last message link** to define where to stop\n"
        "Example: `https://t.me/c/2114152609/10`\n\n"
        "2️⃣ **The number of messages** you want to batch-save from the starting point\n"
        "Example: `10`\n\n"
        "Send `/cancel` to cancel ❌"
    )
    last_ask = await query.message.chat.ask(last_text)
    if await is_input_cancelled(last_ask):
        return

    await setup_custom_task(bot, user_id, first_parts, last_ask.text, notion)


@Client.on_callback_query(filters.regex(r"^bmenu_sync_") & filters.user(Config.OWNER_ID))
async def handle_sync_batch(bot: Client, query: CallbackQuery):
    """Initiates batch sync task starting from last indexed message"""
    notion = query.data.split("_")[-1] == "True"
    user_id = query.from_user.id

    indexed_chats = await db.batch_tasks.get_distinct_chats()
    if not indexed_chats:
        await query.answer("❌ No indexed chats found. Run a Custom Batch first to initialize.", show_alert=True)
        return

    buttons = []
    for chat in indexed_chats:
        chat_id = chat["chat_id"]
        title = chat.get("channel_name") or f"Chat {chat_id}"
        buttons.append([
            InlineKeyboardButton(
                f"📢 {title} ({chat_id})",
                callback_data=f"bsync_run_{chat_id}_{notion}"
            )
        ])

    buttons.append([
        InlineKeyboardButton("🔙 Back", callback_data=f"bmenu_home_{notion}")
    ])

    markup = InlineKeyboardMarkup(buttons)
    await query.message.edit_text(
        "🔄 **Sync Channel from Last Indexed**\n\n"
        "This copies any new messages posted in a chat since your last batch copy.\n\n"
        "Please select the chat/channel you want to sync from the list of previously indexed chats:",
        reply_markup=markup
    )
    await query.answer()


@Client.on_callback_query(filters.regex(r"^bsync_run_") & filters.user(Config.OWNER_ID))
async def handle_run_sync_batch(bot: Client, query: CallbackQuery):
    """Starts the sync batch for the selected chat"""
    data_parts = query.data.split("_")
    chat_id = int(data_parts[2])
    notion = data_parts[3] == "True"
    user_id = query.from_user.id

    # Fetch title from DB for this chat
    indexed_chats = await db.batch_tasks.get_distinct_chats()
    title = "Chat"
    for chat in indexed_chats:
        if chat["chat_id"] == chat_id:
            title = chat.get("channel_name") or "Chat"
            break

    await query.answer("Starting sync batch...", show_alert=False)

    await setup_sync_task(bot, user_id, chat_id, notion, title=title)


@Client.on_callback_query(filters.regex(r"^bmenu_home_") & filters.user(Config.OWNER_ID))
async def handle_bmenu_home(bot: Client, query: CallbackQuery):
    """Goes back to the batch menu"""
    notion_enabled = query.data.split("_")[-1] == "True"
    text, markup = make_batch_menu(notion_enabled)
    await query.message.edit_text(text, reply_markup=markup)
    await query.answer()


@Client.on_callback_query(filters.regex(r"^bmenu_active$") & filters.user(Config.OWNER_ID))
async def handle_bmenu_active(bot: Client, query: CallbackQuery):
    """Shows the active batch task status card"""
    await show_active_task(bot, query.message.chat.id, query.from_user.id, query=query)
    await query.answer()


@Client.on_callback_query(filters.regex(r"^bmenu_completed$") & filters.user(Config.OWNER_ID))
async def handle_bmenu_completed(bot: Client, query: CallbackQuery):
    """Shows the condensed list of completed tasks"""
    await show_completed_tasks(bot, query.message.chat.id, query.from_user.id, query=query)
    await query.answer()


@Client.on_callback_query(filters.regex(r"^b_view_") & filters.user(Config.OWNER_ID))
async def handle_view_task(bot: Client, query: CallbackQuery):
    """Views a specific batch task status card"""
    task_id = int(query.data.split("_")[-1])
    await update_task_ui(query, task_id)
    await query.answer()


async def update_task_ui(query: CallbackQuery, task_id: int):
    """Updates the task details card in the Telegram chat UI"""
    task = await db.batch_tasks.read(task_id)
    if not task:
        return
    await query.message.edit_text(format_task_text(task), reply_markup=make_task_markup(task))


@Client.on_callback_query(filters.regex(r"^b_pause_") & filters.user(Config.OWNER_ID))
async def handle_pause(bot: Client, query: CallbackQuery):
    """Pauses the execution of a running batch task"""
    task_id = int(query.data.split("_")[-1])
    await db.batch_tasks.update_status(task_id, "paused")
    await query.answer("⏸️ Batch paused. Stopping after current item.", show_alert=True)
    await update_task_ui(query, task_id)


@Client.on_callback_query(filters.regex(r"^b_resume_") & filters.user(Config.OWNER_ID))
async def handle_resume(bot: Client, query: CallbackQuery):
    """Resumes a paused/failed batch task in the background"""
    task_id = int(query.data.split("_")[-1])
    user_id = query.from_user.id
    active = await db.batch_tasks.get_active_task(user_id)
    if active:
        return await query.answer("⚠️ You already have a running batch task. Pause it first.", show_alert=True)

    await db.batch_tasks.update_status(task_id, "running")
    await query.answer("▶️ Batch resumed in background.", show_alert=True)
    await start_background_batch(bot, user_id, task_id)
    await update_task_ui(query, task_id)


@Client.on_callback_query(filters.regex(r"^b_cancel_") & filters.user(Config.OWNER_ID))
async def handle_cancel(bot: Client, query: CallbackQuery):
    """Cancels and stops a running batch task"""
    task_id = int(query.data.split("_")[-1])
    await db.batch_tasks.update_status(task_id, "stopped")
    await query.answer("⏹️ Batch task cancelled/stopped.", show_alert=True)
    await update_task_ui(query, task_id)


@Client.on_callback_query(filters.regex(r"^b_delete_") & filters.user(Config.OWNER_ID))
async def handle_delete(bot: Client, query: CallbackQuery):
    """Deletes a batch task record from the database history"""
    task_id = int(query.data.split("_")[-1])
    await db.batch_tasks.delete(task_id)
    await query.answer("❌ Task deleted from history.", show_alert=True)
    await query.message.delete()


@Client.on_callback_query(filters.regex(r"^b_refresh_") & filters.user(Config.OWNER_ID))
async def handle_refresh(bot: Client, query: CallbackQuery):
    """Refreshes the task UI card status"""
    task_id = int(query.data.split("_")[-1])
    try:
        await update_task_ui(query, task_id)
    except Exception:
        pass
    await query.answer("🔄 Status refreshed.")
