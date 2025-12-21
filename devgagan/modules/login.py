# ---------------------------------------------------
# File Name: login.py
# Description: A Pyrogram bot for downloading files from Telegram channels or groups 
#              and uploading them back to Telegram.
# Author: Gagan
# GitHub: https://github.com/devgaganin/
# Telegram: https://t.me/team_spy_pro
# YouTube: https://youtube.com/@dev_gagan
# Created: 2025-01-11
# Last Modified: 2025-01-11
# Version: 2.0.5
# License: MIT License
# ---------------------------------------------------

from pyrogram import filters, Client
from devgagan import app
import random
import os
import asyncio
import string

from devgagan.core.mongo import db
from devgagan.core.mongo.plans_db import is_premium   # ✅ PREMIUM IMPORT
from devgagan.core.func import subscribe, chk_user

from config import API_ID as api_id, API_HASH as api_hash

from pyrogram.errors import (
    ApiIdInvalid,
    PhoneNumberInvalid,
    PhoneCodeInvalid,
    PhoneCodeExpired,
    SessionPasswordNeeded,
    PasswordHashInvalid,
    FloodWait
)

# ------------------ UTILS ------------------

def generate_random_name(length=7):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))


async def delete_session_files(user_id):
    session_file = f"session_{user_id}.session"
    memory_file = f"session_{user_id}.session-journal"

    session_file_exists = os.path.exists(session_file)
    memory_file_exists = os.path.exists(memory_file)

    if session_file_exists:
        os.remove(session_file)

    if memory_file_exists:
        os.remove(memory_file)

    if session_file_exists or memory_file_exists:
        await db.remove_session(user_id)
        return True

    return False

# ------------------ LOGOUT ------------------

@app.on_message(filters.command("logout"))
async def clear_db(client, message):
    user_id = message.chat.id
    files_deleted = await delete_session_files(user_id)

    try:
        await db.remove_session(user_id)
    except Exception:
        pass

    if files_deleted:
        await message.reply("✅ Your session data and files have been cleared from memory and disk.")
    else:
        await message.reply("✅ Logged out successfully.")

# ------------------ LOGIN (PREMIUM ONLY) ------------------

@app.on_message(filters.command("login"))
async def generate_session(_, message):

    user_id = message.from_user.id

    # 🔐 PREMIUM CHECK (MAIN FIX)
    if not await is_premium(user_id):
        return await message.reply(
            "❌ This feature is only available for premium users.\n"
            "Please upgrade to premium to use login."
        )

    joined = await subscribe(_, message)
    if joined == 1:
        return

    number = await _.ask(
        user_id,
        '''Please enter your phone number along with the country code.
Example: +91xxxxxxxxxx , +1xxxxxxxxxx

⚠️ I'll need to send a verification code to this number''',
        filters=filters.text
    )

    phone_number = number.text

    try:
        await message.reply("📲 Sending verification code...")
        client = Client(f"session_{user_id}", api_id, api_hash)
        await client.connect()
    except Exception as e:
        await message.reply(f"❌ Failed to send OTP: {e}")
        return

    try:
        code = await client.send_code(phone_number)
    except ApiIdInvalid:
        await message.reply("❌ Invalid API ID or API HASH.")
        return
    except PhoneNumberInvalid:
        await message.reply("❌ Invalid phone number.")
        return

    try:
        otp_code = await _.ask(
            user_id,
            """📱 Verification Code Sent!

━━━━━━━━━━━━━━━━━━━━
HOW TO ENTER:
• Enter OTP with spaces
• Example: 1 2 3 4 5

Enter OTP:""",
            filters=filters.text,
            timeout=600
        )
    except TimeoutError:
        await message.reply("⏰ Time limit exceeded. Restart login.")
        return

    phone_code = otp_code.text.replace(" ", "")

    try:
        await client.sign_in(phone_number, code.phone_code_hash, phone_code)
    except PhoneCodeInvalid:
        await message.reply("❌ Invalid OTP.")
        return
    except PhoneCodeExpired:
        await message.reply("❌ OTP expired.")
        return
    except SessionPasswordNeeded:
        try:
            two_step = await _.ask(
                user_id,
                "🔐 Two-step verification enabled.\nEnter your password:",
                filters=filters.text,
                timeout=300
            )
            await client.check_password(password=two_step.text)
        except PasswordHashInvalid:
            await message.reply("❌ Incorrect password.")
            return
        except TimeoutError:
            await message.reply("⏰ Password timeout.")
            return

    string_session = await client.export_session_string()
    await db.set_session(user_id, string_session)
    await client.disconnect()

    await otp_code.reply("✅ Login successful!")

