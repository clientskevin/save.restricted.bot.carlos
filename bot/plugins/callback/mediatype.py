from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.enums import MessageMediaType
from bot.utils.media_type import get_media_type, add_media_type, remove_media_type
from database import db
from bot.config import Config


@Client.on_callback_query(filters.regex(r"^mediatype_select$"))
@Client.on_callback_query(filters.regex(r"^mediatype_remove$"))
async def mediatype_toggle_view(bot: Client, query: CallbackQuery):
    """Single page view for toggling media types on/off"""
    current_media_types = await get_media_type()
    
    text = "📋 **Media Type Management**\n\n"
    text += "Toggle media types by clicking on them:\n\n"
    
    buttons = []
    row = []
    
    for i, (media_type_value, display_name) in enumerate(Config.ALL_MEDIA_TYPES.items()):
        is_enabled = media_type_value in current_media_types
        
        if is_enabled:
            button_text = f"✅ {display_name.split(' ')[-1]}"  # Show just the type name with checkmark
            callback_data = f"mediatype_toggle_{media_type_value}_off"
        else:
            button_text = f"❌ {display_name.split(' ')[-1]}"  # Show just the type name with X
            callback_data = f"mediatype_toggle_{media_type_value}_on"
        
        row.append(InlineKeyboardButton(button_text, callback_data=callback_data))
        
        # Create rows of 2 buttons each
        if len(row) == 2 or i == len(Config.ALL_MEDIA_TYPES) - 1:
            buttons.append(row)
            row = []
   
    # Add control buttons
    buttons.append([
        InlineKeyboardButton("Enable All", callback_data="mediatype_enable_all"),
        InlineKeyboardButton("Disable All", callback_data="mediatype_disable_all")
    ])
    buttons.append([
        InlineKeyboardButton("🔄 Reset Default", callback_data="mediatype_reset")
    ])
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="settings")])
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(buttons)
    )


@Client.on_callback_query(filters.regex(r"^mediatype_toggle_(.*)_(on|off)$"))
async def mediatype_toggle_handler(bot: Client, query: CallbackQuery):
    """Toggle a media type on or off"""
    data_parts = query.data.split("_")
    media_type_value = data_parts[2]
    action = data_parts[3]  # 'on' or 'off'
    
    # Convert to MessageMediaType enum
    media_type = None
    if media_type_value == "text":
        media_type = "text"
    else:
        for mt in MessageMediaType:
            if mt.value == media_type_value:
                media_type = mt
                break
    
    if media_type:
        display_name = Config.ALL_MEDIA_TYPES.get(media_type_value, f"Type {media_type_value}")
        
        if action == "on":
            await add_media_type(media_type)
            await query.answer(f"✅ Enabled {display_name}", show_alert=False)
        else:  # action == "off"
            await remove_media_type(media_type)
            await query.answer(f"❌ Disabled {display_name}", show_alert=False)
    else:
        await query.answer("❌ Invalid media type", show_alert=True)
    
    # Refresh the same page
    await mediatype_toggle_view(bot, query)


@Client.on_callback_query(filters.regex(r"^mediatype_enable_all$"))
async def mediatype_enable_all(bot: Client, query: CallbackQuery):
    """Enable all media types"""
    all_media_types = list(Config.ALL_MEDIA_TYPES.keys())
    
    # Set all media types as enabled
    await db.config.col.update_one(
        {"name": "media_type"}, 
        {"$set": {"value": all_media_types}},
        upsert=True
    )
    
    await query.answer("✅ All media types enabled!", show_alert=True)
    await mediatype_toggle_view(bot, query)


@Client.on_callback_query(filters.regex(r"^mediatype_disable_all$"))
async def mediatype_disable_all(bot: Client, query: CallbackQuery):
    """Disable all media types"""
    # Set empty list
    await db.config.col.update_one(
        {"name": "media_type"}, 
        {"$set": {"value": []}},
        upsert=True
    )
    
    await query.answer("❌ All media types disabled!", show_alert=True)
    await mediatype_toggle_view(bot, query)


@Client.on_callback_query(filters.regex(r"^mediatype_reset$"))
async def mediatype_reset(bot: Client, query: CallbackQuery):
    """Reset media types to default values"""
    default_media_types = [
        MessageMediaType.PHOTO.value,
        MessageMediaType.VIDEO.value,
        MessageMediaType.AUDIO.value,
        MessageMediaType.DOCUMENT.value,
        "text"
    ]
    
    # Clear existing and set default
    await db.config.col.update_one(
        {"name": "media_type"}, 
        {"$set": {"value": default_media_types}},
        upsert=True
    )
    
    await query.answer("🔄 Reset to default media types!", show_alert=True)
    await mediatype_toggle_view(bot, query)


@Client.on_callback_query(filters.regex(r"^mediatype_main$"))
async def mediatype_main(bot: Client, query: CallbackQuery):
    """Main media type management - redirect to toggle view"""
    await mediatype_toggle_view(bot, query) 