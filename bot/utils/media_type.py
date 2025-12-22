from database import db
from pyrogram.enums import MessageMediaType
from bot.config import Config

name = "media_type"

async def get_media_type():
    r = await db.config.get_or_create_config(name, list(Config.ALL_MEDIA_TYPES.keys()))
    return r["value"]

async def add_media_type(media_type: MessageMediaType | str):
    if isinstance(media_type, MessageMediaType):
        media_type = media_type.value
    await db.config.col.update_one({"name": name}, {"$push": {"value": media_type}})
    return True

async def remove_media_type(media_type: MessageMediaType | str):
    if isinstance(media_type, MessageMediaType):
        media_type = media_type.value
    await db.config.col.update_one({"name": name}, {"$pull": {"value": media_type}})
    return True

