from pyrogram import Client, filters
from pyrogram.types import Message
from bot.config import Config


@Client.on_message(
    filters.command("admin") & filters.private & filters.user(Config.OWNER_ID)
)
@Client.on_callback_query(filters.regex("^admin"))
async def admin(client: Client, message: Message):
    text = """
**Admin Commands**

👥 Admins:
/addadmin - Add an admin
/admins - Get all admins
/removeadmin - Remove an admin

👤 Users:
/users - Get all users
/user - Get User Details, Ban/Unban User

📢 Others:
/broadcast - Broadcast a message to all users
/mediatype - Manage the media type to be forwarded
    """ 

    await client.reply(message, text)
