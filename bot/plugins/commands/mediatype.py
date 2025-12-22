from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.enums import MessageMediaType
from bot.config import Config
from bot.utils.media_type import get_media_type


@Client.on_message(filters.command("mediatype") & filters.private & filters.user(Config.OWNER_ID))
async def mediatype_command(bot: Client, message: Message):
    """Command to manage media types that the bot will save"""
    current_media_types = await get_media_type()
    
    # Available media types
    all_media_types = {
        MessageMediaType.PHOTO.value: "📷 Photo",
        MessageMediaType.VIDEO.value: "🎥 Video", 
        MessageMediaType.AUDIO.value: "🎵 Audio",
        MessageMediaType.DOCUMENT.value: "📄 Document",
        MessageMediaType.ANIMATION.value: "🎞️ Animation",
        MessageMediaType.VOICE.value: "🎤 Voice",
        MessageMediaType.VIDEO_NOTE.value: "📹 Video Note",
        MessageMediaType.STICKER.value: "🎨 Sticker",
        MessageMediaType.POLL.value: "📊 Poll",
        MessageMediaType.LOCATION.value: "📍 Location",
        MessageMediaType.CONTACT.value: "👤 Contact",
        MessageMediaType.VENUE.value: "🏢 Venue",
        MessageMediaType.GAME.value: "🎮 Game",
        MessageMediaType.DICE.value: "🎲 Dice",
        MessageMediaType.WEB_PAGE.value: "🌐 Web Page",
    }
    
    text = "📋 **Media Type Management**\n\n"
    text += "Current enabled media types:\n"
    
    if current_media_types:
        for media_type in current_media_types:
            if media_type in all_media_types:
                text += f"• {all_media_types[media_type]}\n"
    else:
        text += "• None selected\n"
    
    text += f"\nTotal: {len(current_media_types)} types enabled"
    
    buttons = [
        [InlineKeyboardButton("⚙️ Manage Media Types", callback_data="mediatype_select")],
        [InlineKeyboardButton("🔙 Back", callback_data="settings")]
    ]
    
    await bot.reply(
        message,
        text,
        reply_markup=InlineKeyboardMarkup(buttons)
    )