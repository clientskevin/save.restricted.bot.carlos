import os
import time

from pyrogram import Client, types

from bot.config import Config
from bot.exceptions import CancelledError
from bot.utils.archive_handler import is_archive
from bot.utils.ffmpeg import get_video_details
from bot.utils.helpers import *
from bot.utils.notion import upload_archive_to_notion, upload_message_to_notion
from database import db

from .media_type import get_media_type
import logging

logger = logging.getLogger(__name__)

async def forward_message(
    bot: Client, app: Client, message: types.Message, user_id: int, notion_enabled: bool
):
    valid_channels = []

    user_channels = await db.user_channels.filter_documents({"user_id": user_id})
    for channel in user_channels:
        if not channel["status"]:
            continue

        try:
            await bot.get_chat(channel["channel_id"])
        except Exception as e:
            await bot.floodwait_handler(
                bot.send_message,
                user_id,
                f"Chat not found - {channel['channel_id']}",
            )
            continue

        valid_channels.append(channel)

    if not valid_channels:
        valid_channels.append(
            {
                "channel_id": user_id,
                "topic_id": None,
                "paid_media": {
                    "status": False,
                    "stars": 0,
                },
            }
        )

    file_path = None
    notion_file_id = None

    if message.text:
        log = await bot.send_message(
            Config.FILES_LOG, message.text, reply_markup=message.reply_markup
        )
    else:
        file_path = await download_media(bot, user_id, message)
        logger.info(f"Downloaded media file: {file_path}: {message.link}")
        if file_path:
            log, file_path = await upload_media(  # pyright: ignore[reportGeneralTypeIssues]
                user_id,
                bot,
                app,
                file_path,
                channel_id=Config.FILES_LOG,
                message=message,
            )
        else:
            return 

    # Upload to Notion and save to DB

    archive_metadata = None
    
    if file_path and notion_enabled: # upload even if it already exists cause file expires after 30 days
        try:
            # Check if file is an archive (.zip or .rar)
            if is_archive(file_path):
                print(f"📦 Detected archive file: {os.path.basename(file_path)}")
                archive_result = upload_archive_to_notion(file_path)
                if archive_result and archive_result.file_ids:
                    # Store the first file ID as the primary media_url
                    notion_file_id = archive_result.file_ids[0]
                    print(f"✅ Uploaded {archive_result.total_files} files from archive")
                    # Store archive metadata for the indexer
                    archive_metadata = {
                        "file_ids": archive_result.file_ids,
                        "file_names": archive_result.file_names,
                        "archive_name": archive_result.archive_name,
                        "total_files": archive_result.total_files
                    }
            else:
                # Regular file upload
                notion_result = upload_message_to_notion(message, file_path)
                if notion_result:
                    notion_file_id = notion_result.file_id
        except Exception as e:
            print(f"Notion upload failed: {e}")

    if notion_enabled:
        # Save or update message metadata to DB with Notion file ID and archive metadata
        await db.messages.get_or_update_from_pyrogram(
            message, 
            file_id=notion_file_id,
            archive_files=archive_metadata
        )

    if not log:
        return await bot.send_message(
            user_id, "Failed to forward the message. Please try again."
        )

    caption = log.text or log.caption or ""

    for channel in valid_channels:
        topic_id = channel["topic_id"]
        paid_star = (
            channel["paid_media"]["stars"] if channel["paid_media"]["status"] else None
        )
        kwargs = {}

        if not topic_id:
            await handle_topic_thread(app, message, channel["channel_id"], kwargs)
        else:
            kwargs["message_thread_id"] = topic_id

        if paid_star and (message.photo or message.video):
            # send using paid media
            if message.photo:
                media = types.InputMediaPhoto(log.photo.file_id)
            elif message.video:
                media = types.InputMediaVideo(log.video.file_id)
            await bot.floodwait_handler(
                bot.send_paid_media,
                chat_id=channel["channel_id"],
                stars_amount=paid_star,
                media=[media],
                caption=caption,
                reply_to_message_id=topic_id,
                **kwargs,
            )
        elif message.media:
            r = await bot.floodwait_handler(
                log.copy,
                channel["channel_id"],
                caption=caption,
                reply_markup=message.reply_markup,
                **kwargs,
            )
        else:
            await bot.floodwait_handler(
                bot.send_message,
                channel["channel_id"],
                caption,
                reply_markup=message.reply_markup,
                **kwargs,
            )

    if file_path:
        os.remove(file_path)

    if is_transfer_cancelled(message.download_id):
        raise CancelledError


async def download_media(bot, user_id, message: types.Message):
    download_id = message.download_id  # This is the download id of the message

    media = message.document or message.video or message.photo or message.audio
    if not media:
        return None

    out = await bot.floodwait_handler(
        bot.send_message, user_id, f"Downloading ({message.index})"
    )
    start = time.time()

    filename = get_file_name(message)

    if not filename:
        await out.delete()
        await bot.send_message(user_id, "No file name found.")
        return None

    file_path = await bot.floodwait_handler(
        message.download,
        file_name=filename,
        progress=progress_for_pyrogram,
        progress_args=(
            start,
            message,
            out.edit,
            download_id,
            f"Downloading ({message.index})",
        ),
    )
    await out.delete()
    if not file_path:
        if is_transfer_cancelled(download_id):
            raise CancelledError
    return file_path


async def upload_media(
    user_id,
    bot: Client,
    app: Client,
    file_path: str,
    channel_id: int,
    message: types.Message,
):
    out = await bot.floodwait_handler(bot.send_message, user_id, "Starting upload...")

    upload_instance = app
    function = None

    tg_user = await bot.get_users(user_id)
    thumbnail = await get_thumbnail(file_path)

    function, kwargs = await get_upload_function(message, upload_instance, file_path)

    if not function:
        await out.delete()
        return await bot.send_message(
            user_id, "Invalid file upload mode. Please select a valid file upload mode."
        )

    if function == upload_instance.send_video:
        width, height, duration = await get_video_details(file_path)
        kwargs["duration"] = duration
        kwargs["width"] = width
        kwargs["height"] = height

    kwargs["chat_id"] = channel_id

    await handle_topic_thread(app, message, channel_id, kwargs)

    media = ["audio", "document", "video", "photo"]
    if any(media_type in kwargs for media_type in media) and thumbnail:
        kwargs["thumb"] = thumbnail

    title = get_title(message)

    if title:
        kwargs["file_name"] = title

    kwargs["progress"] = progress_for_pyrogram
    kwargs["progress_args"] = (
        time.time(),
        message,
        out.edit,
        message.download_id,
        f"Uploading ({message.index})",
    )
    print("upload start")

    caption = message.text or message.caption or ""

    media_type = await get_media_type()

    if "text" in media_type:
        kwargs["caption"] = caption

    await bot.floodwait_handler(out.edit, "Uploading...")

    log = await bot.floodwait_handler(function, **kwargs)
    await out.delete()
    if thumbnail:
        os.remove(thumbnail)
    if not log:
        if is_transfer_cancelled(message.download_id):
            raise CancelledError
        else:
            raise Exception("Failed to upload message")

    log = await bot.get_messages(log.chat.id, log.id)
    return log, file_path


async def resume_transfers(bot: Client):
    transfers = await db.transfers.filter_documents(
        {
            "status": {
                "$in": [TransferStatus.SLEEPING.value, TransferStatus.IN_PROGRESS.value]
            }
        }
    )
    for transfer in transfers:
        user_id = transfer["user_id"]
        text = f"**Bot has been restarted. You can resume your transfers now from {transfer['link_index']} to {len(transfer['links'])}.**"
        markup = types.InlineKeyboardMarkup(
            [
                [
                    types.InlineKeyboardButton(
                        "Resume Transfers",
                        callback_data=f"resume_transfers {transfer['_id']}",
                    )
                ]
            ]
        )
        try:
            await bot.send_message(user_id, text, reply_markup=markup)
        except Exception as e:
            print(e)

        await update_transfer(transfer["_id"], status=None)


async def add_transfer_to_queue(
    user_id, download_id, links, link_index, status, **kwargs
):
    Config.TRANSFERS[download_id] = {
        "user_id": user_id,
        "links": links,
        "link_index": link_index,
        "status": status,
    }

    return await db.transfers.create(
        user_id, download_id, links, link_index, status, **kwargs
    )


async def remove_transfer_from_queue(download_id):
    Config.TRANSFERS.pop(download_id, None)
    return await db.transfers.delete(download_id)


async def update_transfer(download_id, **kwargs):
    if download_id in Config.TRANSFERS:
        Config.TRANSFERS[download_id].update(kwargs)
    return await db.transfers.update(download_id, kwargs)


def get_file_name(message: types.Message):
    if not message.media:
        return None

    media = getattr(message, message.media.value, None)
    if not media:
        return None

    file_name = getattr(media, "file_name", None)

    if file_name:
        return file_name

    # Mapping of media types to their extensions
    media_extensions = {"photo": ".jpg", "video": ".mp4", "audio": ".mp3"}

    # Get the media type and extension
    media_type = message.media.value
    if media_type in media_extensions:
        return f"{media.file_id}{media_extensions[media_type]}"

    return None


def get_extension(file_name):
    return file_name.split(".")[-1]


async def get_topics_by_chat_id(client: Client, chat_id: int):
    """Get all topics from a chat and return a dict mapping topic names to topic IDs"""
    from typing import Dict

    topics: Dict[str, int] = {}
    try:
        async for topic in client.get_forum_topics(chat_id):
            topics[topic.title] = topic.id
    except Exception as e:
        print(f"Error getting topics from chat {chat_id}: {e}")

    return topics


async def get_source_topics(client: Client, source_chat_id: int):
    """Get all topics from the source channel"""
    return await get_topics_by_chat_id(client, source_chat_id)


async def get_target_topics(client: Client, target_chat_id: int):
    """Get all topics from the target chat"""
    return await get_topics_by_chat_id(client, target_chat_id)


async def handle_topic_thread(
    app: Client, message: types.Message, channel_id: int, kwargs: dict
):
    """Handle topic/thread assignment for messages.

    Args:
        app: Pyrogram client
        message: Source message
        channel_id: Target channel ID
        kwargs: Dictionary to update with message_thread_id
    """
    source_topic = message.topic and message.topic.id
    if source_topic:
        source_topic_name = message.topic.title
        target_topics = await get_target_topics(app, channel_id)
        target_topic = await create_topic_if_not_exists(
            app, channel_id, source_topic_name, target_topics
        )
        if target_topic:
            kwargs["message_thread_id"] = target_topic


async def create_topic_if_not_exists(
    client: Client, target_chat_id: int, topic_name: str, existing_topics: dict
):
    """
    Create a topic in the target chat if it doesn't already exist.
    Returns the topic ID (either existing or newly created).

    Args:
        client: Pyrogram client
        target_chat_id: Target chat ID
        topic_name: Name of the topic to create
        existing_topics: Dict of existing topics {name: id}

    Returns:
        int: Topic ID
    """
    # Check if topic already exists
    if topic_name in existing_topics:
        print(
            f"Topic '{topic_name}' already exists with ID {existing_topics[topic_name]}"
        )
        return existing_topics[topic_name]

    # Create new topic
    try:
        topic = await client.create_forum_topic(
            chat_id=target_chat_id, title=topic_name
        )
        print(f"Created new topic '{topic_name}' with ID {topic.id}")
        existing_topics[topic_name] = topic.id  # Update the cache
        return topic.id
    except Exception as e:
        print(f"Error creating topic '{topic_name}': {e}")
        return None
