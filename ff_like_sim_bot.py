#!/usr/bin/env python3
"""
Safe educational Telegram bot that simulates 'likes' for UIDs locally.
Does NOT connect to Free Fire servers.
"""

import sqlite3
import logging
import os
from datetime import datetime
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# -------------------------
# CONFIG
# -------------------------
BOT_TOKEN = "8115790971:AAFO62ui_Vv1KUabC8fYrmZkhhFWdga4dyY"
OWNER_ID = 6856782189
DB_PATH = "likes_sim.db"
# -------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -------------------------
# Database setup
# -------------------------
def init_db():
    create = not os.path.exists(DB_PATH)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    if create:
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            region TEXT NOT NULL,
            uid TEXT NOT NULL,
            likes INTEGER NOT NULL DEFAULT 0,
            last_updated TEXT
        )
        """)
        cur.execute("""
        CREATE TABLE logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            username TEXT,
            command TEXT,
            region TEXT,
            uid TEXT,
            timestamp TEXT
        )
        """)
        conn.commit()
    return conn

DB = init_db()

def log_command(user_id, username, command, region, uid):
    ts = datetime.utcnow().isoformat()
    DB.execute(
        "INSERT INTO logs (telegram_id, username, command, region, uid, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, username, command, region, uid, ts),
    )
    DB.commit()

def increment_likes(region, uid, delta=1):
    cur = DB.cursor()
    cur.execute("SELECT likes FROM likes WHERE region=? AND uid=?", (region, uid))
    row = cur.fetchone()
    now = datetime.utcnow().isoformat()
    if row:
        new = row[0] + delta
        cur.execute("UPDATE likes SET likes=?, last_updated=? WHERE region=? AND uid=?",
                    (new, now, region, uid))
    else:
        new = delta
        cur.execute("INSERT INTO likes (region, uid, likes, last_updated) VALUES (?, ?, ?, ?)",
                    (region, uid, new, now))
    DB.commit()
    return new

def get_likes(region, uid):
    cur = DB.cursor()
    cur.execute("SELECT likes FROM likes WHERE region=? AND uid=?", (region, uid))
    row = cur.fetchone()
    return row[0] if row else 0

def get_top(n=10):
    cur = DB.cursor()
    cur.execute("SELECT region, uid, likes FROM likes ORDER BY likes DESC LIMIT ?", (n,))
    return cur.fetchall()

def get_user_logs(user_id, limit=20):
    cur = DB.cursor()
    cur.execute("SELECT command, region, uid, timestamp FROM logs WHERE telegram_id=? ORDER BY id DESC LIMIT ?",
                (user_id, limit))
    return cur.fetchall()

# -------------------------
# Access control
# -------------------------
def require_owner(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if user.id != OWNER_ID:
            await update.message.reply_text("❌ You are not authorized to use this bot.")
            return
        return await func(update, context)
    return wrapper

# -------------------------
# Bot Commands
# -------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Free Fire Likes Simulator\n\n"
        "Commands:\n"
        "/like <region> <uid> → simulate giving likes\n"
        "/count <region> <uid> → check total likes\n"
        "/top → show top UIDs\n"
        "/mylogs → show your recent commands\n\n"
        "⚠️ Note: This is only a simulator for education!"
    )

@require_owner
async def like_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Usage: /like <region> <uid>")
        return
    region, uid = args[0].lower(), args[1]
    if not uid.isdigit():
        await update.message.reply_text("UID must be numeric.")
        return
    total = increment_likes(region, uid, 1)
    log_command(update.effective_user.id, update.effective_user.username, "/like", region, uid)
    await update.message.reply_text(f"✅ Added 1 simulated like to UID {uid} ({region}).\nTotal = {total}")

@require_owner
async def count_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Usage: /count <region> <uid>")
        return
    region, uid = args[0].lower(), args[1]
    total = get_likes(region, uid)
    log_command(update.effective_user.id, update.effective_user.username, "/count", region, uid)
    await update.message.reply_text(f"📊 UID {uid} ({region}) has {total} simulated likes.")

@require_owner
async def top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = get_top(10)
    if not rows:
        await update.message.reply_text("No data yet.")
        return
    lines = [f"{i+1}. {uid} ({region}) → {likes} likes" for i, (region, uid, likes) in enumerate(rows)]
    await update.message.reply_text("🏆 Top liked UIDs:\n" + "\n".join(lines))

@require_owner
async def mylogs_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = get_user_logs(update.effective_user.id)
    if not rows:
        await update.message.reply_text("No logs yet.")
        return
    lines = [f"{ts} → {cmd} {region} {uid}" for cmd, region, uid, ts in rows]
    await update.message.reply_text("\n".join(lines))

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Unknown command. Use /start")

# -------------------------
# Run bot
# -------------------------
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("like", like_cmd))
    app.add_handler(CommandHandler("count", count_cmd))
    app.add_handler(CommandHandler("top", top_cmd))
    app.add_handler(CommandHandler("mylogs", mylogs_cmd))
    app.add_handler(MessageHandler(filters.COMMAND, unknown))
    print("🚀 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
