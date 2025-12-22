from pyrogram.types import Message
from pyrogram import Client, filters
from asyncio.exceptions import TimeoutError
from pyrogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButton,
)
from pyrogram.errors import (
    PhoneNumberInvalid,
    PhoneCodeInvalid,
    PhoneCodeExpired,
    SessionPasswordNeeded,
    PasswordHashInvalid,
)
from bot import User
from database import db


class Data:
    generate_single_button = [
        InlineKeyboardButton("🔒 Secure Login", callback_data="connect_account")
    ]

    home_buttons = [
        [InlineKeyboardButton("🔐 Account", callback_data="connected_account")],
        [InlineKeyboardButton(text="🏠 Return Home 🏠", callback_data="start")],
    ]

    generate_button = [generate_single_button]


async def generate_session(bot: Client, msg: Message):

    user_id = msg.from_user.id

    api_id = bot.api_id
    api_hash = bot.api_hash

    t = "📲 Now please send your Phone number along with the country code. \nExample: `+19876543210`"
    t += f"\n\nNote: **Use the same number as the account you are now using.**"
    t += "\n\n/cancel to cancel ❌"

    phone_number_msg: Message = await bot.ask(
        user_id,
        t,
        filters=filters.text | filters.contact,
        reply_markup=ReplyKeyboardMarkup(
            [[KeyboardButton("Send Phone Number", request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
        timeout=300,
    )
    if await cancelled(phone_number_msg):
        return

    if phone_number_msg.contact:
        phone_number = phone_number_msg.contact.phone_number
    else:
        phone_number = phone_number_msg.text

    await msg.reply("🔐 Logging in as User...", reply_markup=ReplyKeyboardRemove())

    client = Client(
        name=f"user_{user_id}", api_id=api_id, api_hash=api_hash, in_memory=True
    )

    await client.connect()
    try:
        code = None
        code = await client.send_code(phone_number)
    except PhoneNumberInvalid:
        await msg.reply(
            "🚫 Phone number is invalid. Please start generating the session again.",
            reply_markup=InlineKeyboardMarkup(Data.generate_button),
        )
        return
    try:
        phone_code_msg = None
        phone_code_msg = await bot.ask(
            user_id,
            "📩 Please check for an OTP in the official Telegram app. Once received, send the OTP here in the following format: If OTP is `12345`, **please send it as** `1 2 3 4 5`.",
            filters=filters.text,
            timeout=600,
        )
        if await cancelled(phone_code_msg):
            return
    except TimeoutError:
        await msg.reply(
            "⏰ Time limit reached (10 minutes). Please start generating the session again.",
            reply_markup=InlineKeyboardMarkup(Data.generate_button),
        )
        return

    if " " not in phone_code_msg.text:
        await phone_code_msg.reply(
            "🚫 Invalid OTP format. If OTP is `12345`, **please send it as** `1 2 3 4 5`.",
            quote=True,
            reply_markup=InlineKeyboardMarkup(Data.generate_button),
        )
        return

    phone_code = phone_code_msg.text.replace(" ", "")
    try:
        await client.sign_in(phone_number, code.phone_code_hash, phone_code)
    except PhoneCodeInvalid:
        await msg.reply(
            "❌ OTP is invalid. Please start generating the session again.",
            reply_markup=InlineKeyboardMarkup(Data.generate_button),
        )
        return
    except PhoneCodeExpired:
        await msg.reply(
            "⌛ OTP has expired. Please start generating the session again.",
            reply_markup=InlineKeyboardMarkup(Data.generate_button),
        )
        return
    except SessionPasswordNeeded:
        try:
            two_step_msg = await bot.ask(
                user_id,
                "🔐 Your account has two-step verification enabled. Please provide the password.",
                filters=filters.text,
                timeout=300,
            )
        except TimeoutError:
            await msg.reply(
                "⏰ Time limit reached (5 minutes). Please start generating the session again.",
                reply_markup=InlineKeyboardMarkup(Data.generate_button),
            )
            return
        try:
            password = two_step_msg.text
            await client.check_password(password=password)
        except PasswordHashInvalid:
            await two_step_msg.reply(
                "🚫 Invalid Password Provided. Please start generating the session again.",
                quote=True,
                reply_markup=InlineKeyboardMarkup(Data.generate_button),
            )
            return

    string_session = await client.export_session_string()
    me = await client.get_me()

    if me.id != user_id:
        await msg.reply(
            "🚫 You are not the owner of the account. Please start generating the session again with your own number",
            reply_markup=InlineKeyboardMarkup(Data.generate_button),
        )
        return

    await db.users.update(
        user_id,
        {
            "session.string": string_session,
            "session.id": me.id,
            "session.username": me.username,
        },
    )

    await bot.send_message(
        msg.chat.id,
        "🎉 Successfully logged in! Please continue with the buttons below.",
        reply_markup=InlineKeyboardMarkup(Data.home_buttons),
    )

    client = User(string_session, name=f"user_{user_id}")
    await client.start()


async def cancelled(msg):
    if not msg.text:
        return
    if "/cancel" in msg.text:
        await msg.reply(
            "🚫 Generation process cancelled!",
            quote=True,
            reply_markup=ReplyKeyboardRemove(),
        )
        await msg.reply(
            "You can login again by clicking the button below.",
            quote=True,
            reply_markup=InlineKeyboardMarkup(Data.generate_button),
        )
        return True
    elif msg.text.startswith("/"):  # Bot Commands
        await msg.reply(
            "🚫 Generation process cancelled!",
            quote=True,
            reply_markup=ReplyKeyboardRemove(),
        )
        return True
    else:
        return False
