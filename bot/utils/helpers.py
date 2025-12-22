import functools
import logging
import math
import os
import random
import time

from aiohttp import web
from pyrogram import Client, StopTransmission, types
from pyrogram.types import InputMediaPhoto, InputMediaVideo

from bot.config import Config, Script
from bot.enums import TransferStatus
from bot.utils.ffmpeg import create_thumbnail
from database import db


async def get_thumbnail(file_path):
    """Create thumbnail only for video files"""
    # Check if file is a video by extension
    video_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.webm', '.m4v', '.mpg', '.mpeg']
    
    if not any(file_path.lower().endswith(ext) for ext in video_extensions):
        # Not a video file, skip thumbnail creation
        return None
    
    # Only create thumbnail for video files
    thumbnail = await create_thumbnail(file_path)
    return thumbnail


async def set_commands(app: Client):
    commands = [
        types.BotCommand("start", "🚀 Get started with the bot"),
        types.BotCommand("help", "💡 Need assistance? Find help here"),
        types.BotCommand("settings", "⚙️ Manage your settings"),
        types.BotCommand("batch", "📦 Save an entire channel"),
        types.BotCommand("account", "👤 Manage your Telegram account"),
        types.BotCommand("channels", "📢 Manage your channels like a pro"),
        types.BotCommand("cancel", "❌ Cancel an ongoing transfer"),
    ]
    await app.set_bot_commands(commands, scope=types.BotCommandScopeAllPrivateChats())


async def get_admins():
    config = await db.config.get_config("ADMINS")
    return config["value"]


async def add_admin(user_id):
    config = await db.config.get_config("ADMINS")
    if config:
        admins = config["value"]
        if user_id not in admins:
            admins.append(user_id)
            await db.config.update_config("ADMINS", admins)
            return True
    else:
        await db.config.add_config("ADMINS", [user_id])
        return True

    return False


async def remove_admin(user_id):
    config = await db.config.get_config("ADMINS")
    if config:
        admins = config["value"]
        if user_id in admins:
            admins.remove(user_id)
            await db.config.update_config("ADMINS", admins)
            return True
    return False


async def start_webserver():
    routes = web.RouteTableDef()

    @routes.get("/", allow_head=True)
    async def root_route_handler(request):
        res = {
            "status": "running",
        }
        return web.json_response(res)

    async def web_server():
        web_app = web.Application(client_max_size=30000000)
        web_app.add_routes(routes)
        return web_app

    app = web.AppRunner(await web_server())
    await app.setup()
    await web.TCPSite(app, "0.0.0.0", 8000).start()
    logging.info("Web server started")


async def add_user(bot: Client, user: types.User):
    user_id = user.id

    is_exist = await db.users.read(user_id)

    if is_exist:
        return

    await db.users.create(user_id)

    text = "New user!\n\n"
    text += f"Name: {user.first_name}\n"
    text += f"ID: `{user_id}`\n"
    text += f"Mention: {user.mention}\n"

    await bot.send_message(Config.USER_INFO_LOG, text)

    return True


async def download_thumbnail(app: Client, thumbnail_id: int):
    try:
        thumbnail = await app.download_media(thumbnail_id)
    except Exception as e:
        print(e)
        os.remove(thumbnail)
        thumbnail = None
    return thumbnail


async def progress_for_pyrogram(
    current, total, start, file_message, edit_func, download_id, mode="Uploading"
):
    if is_transfer_cancelled(download_id):
        raise StopTransmission
    # if total is less than 50mb. then do nothing
    if total < 50000000:
        return

    file_message: types.Message = file_message
    progress_data = [
        ("■", "□"),
        ("★", "❍"),
        ("✿", "○"),
        ("❥", "♡"),
        ("♛", "❍"),
        ("✪", "❍"),
        ("★", "✩"),
    ]
    progress_bar = random.choice(progress_data)
    now = time.time()
    diff = now - start
    a, b = progress_bar

    if round(diff % 25.00) == 0 or current == total:
        percentage = current * 100 / total
        speed = current / diff
        elapsed_time = round(diff) * 1000
        time_to_completion = round((total - current) / speed) * 1000
        estimated_total_time = time_to_completion

        elapsed_time = TimeFormatter(milliseconds=elapsed_time)
        estimated_total_time = TimeFormatter(milliseconds=estimated_total_time)

        progress = "{0}{1}\n".format(
            "".join([a for _ in range(math.floor(percentage / (100 / 15)))]),
            "".join([b for _ in range(15 - math.floor(percentage / (100 / 15)))]),
        ).strip()

        tmp = Script.PROGRESS_MESSAGE

        tmp = tmp.format(
            mode=mode,
            percentage=round(percentage, 2),
            progress=progress,
            speed=humanbytes(speed),
            eta=estimated_total_time if estimated_total_time != "" else "0 s",
            finished=humanbytes(current),
            total=humanbytes(total),
        )

        try:
            await edit_func(
                tmp,
                reply_markup=types.InlineKeyboardMarkup(
                    [
                        [
                            types.InlineKeyboardButton(
                                "Cancel", callback_data=f"cancel {download_id}"
                            )
                        ]
                    ]
                ),
                disable_web_page_preview=True,
            )
        except Exception as e:
            print(e)


async def get_user_client(user_id) -> Client:
    user = await db.users.read(user_id)
    if not user:
        return

    session_id = user["session"].get("id")
    client = Config.CLIENTS.get(session_id)
    return client


async def is_input_cancelled(message: types.Message):
    if message.text and message.text.lower() == "/cancel":
        return await message.reply_text("❌ Operation cancelled.", quote=True)
    return False


async def get_upload_function(message: types.Message, app: Client, file_path: str):

    media = message.document or message.video or message.photo or message.audio
    if not media:
        return None

    if message.document:
        return app.send_document, {"document": file_path}
    elif message.video:
        return app.send_video, {"video": file_path}
    elif message.audio:
        return app.send_audio, {"audio": file_path}
    elif message.photo:
        return app.send_photo, {"photo": file_path}
    else:
        return None


def get_media(message: types.Message):
    if not message.media:
        return
    return getattr(message, message.media.value)


def get_extension(message: types.Message):
    media = get_media(message)
    if not media:
        return ""
    file_name = getattr(media, "file_name", None)
    mimetype = getattr(media, "mime_type", None)
    if file_name:
        return file_name.split(".")[-1]
    if mimetype:
        return mimetype.split("/")[-1]
    return ""


def is_transfer_cancelled(download_id):
    if (
        Config.TRANSFERS.get(download_id, {}).get("status")
        == TransferStatus.CANCELLED.value
    ):
        Config.TRANSFERS.pop(download_id)
        return True


def check_admin(func):
    """Check if user is admin or not"""

    @functools.wraps(func)
    async def wrapper(client: Client, message):
        chat_id = getattr(message.from_user, "id", None)
        admins = await get_admins()

        if chat_id not in admins:
            return await message.reply_text("You are not allowed to use this command.")
        return await func(client, message)

    return wrapper


def get_title(message: types.Message):
    title = message.document or message.video or message.audio
    if not title:
        return
    title = getattr(title, "file_name", None)
    return title


def is_valid_link(message):
    domains = ["t.me", "telegram.me", "telegram.dog", "tg://"]
    if not any(domain in message.text for domain in domains):
        return False
    return True


def get_link_parts(link: str):
    topic_id = None

    if link.startswith("tg://"):
        # Handle tg:// links
        if not "openmessage?" in link:
            return

        try:
            params = dict(param.split("=") for param in link.split("?")[1].split("&"))
            chat_id = params.get("user_id")
            if chat_id.isdigit():
                chat_id = int(chat_id)
            else:
                chat_id = chat_id.replace("@", "")
            message_id = int(params.get("message_id"))
            return chat_id, message_id, topic_id
        except:
            return

    if not link.startswith("http"):
        return

    link = (
        link.replace("https://", "")
        .replace("http://", "")
        .replace("/c/", "/")
        .replace("/s/", "/")
        .replace("/b/", "/")
        .strip()
    )
    link = link.split("?")[0]
    link = link.split("/")

    if not len(link) >= 3:
        return

    chat_id = link[1]
    message_id = link[2]

    if len(link) == 4:
        topic_id = int(link[3])

    if chat_id.isdigit():
        chat_id = int(f"-100{chat_id}")

    try:
        message_id = int(message_id)
    except ValueError:
        return

    return chat_id, message_id, topic_id


def get_link_parts_from_forward(message: types.Message):
    chat_id = message.forward_from_chat.id
    message_id = message.forward_from_message_id
    return chat_id, message_id, None


def is_command(message):
    if message.text.startswith("/"):
        return True
    return False


def get_mime_type(message: types.Message):
    media = message.document or message.video or message.audio
    if not media:
        return ""
    return media.mime_type.split("/")[0]


def TimeFormatter(milliseconds: int) -> str:
    seconds, milliseconds = divmod(milliseconds, 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    tmp = (
        (f"{str(days)}d, " if days else "")
        + (f"{str(hours)}hr, " if hours else "")
        + (f"{str(minutes)}min, " if minutes else "")
        + (f"{str(seconds)}s, " if seconds else "")
    )
    return tmp[:-2]


def humanbytes(size):
    if not size:
        return "0 B"
    power = 2**10
    n = 0
    Dic_powerN = {0: " ", 1: "Ki", 2: "Mi", 3: "Gi", 4: "Ti"}
    while size > power:
        size /= power
        n += 1
    return f"{str(round(size, 2))} {Dic_powerN[n]}B"


def parse_duration(duration: str) -> int:
    duration = duration.lower()
    if duration.endswith("d"):
        return int(duration[:-1]) * 86400
    elif duration.endswith("w"):
        return int(duration[:-1]) * 604800
    elif duration.endswith("m"):
        return int(duration[:-1]) * 2592000
    elif duration.endswith("y"):
        return int(duration[:-1]) * 31536000
    elif duration.endswith("h"):
        return int(duration[:-1]) * 3600
    else:
        return int(duration)
