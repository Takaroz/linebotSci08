from flask import Flask, request, jsonify
import re
import sqlite3
from datetime import datetime, timedelta
import threading
import time
import os
import requests

app = Flask(__name__)

# LINE ACCESS TOKEN
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_REPLY_URL = "https://api.line.me/v2/bot/message/reply"

# --- สร้างฐานข้อมูล ---
def init_db():
    with sqlite3.connect("database.db") as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                detail TEXT,
                due_date TEXT
            )
        ''')
init_db()

def reply_to_line(reply_token, message_text):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }
    body = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": message_text}]
    }
    requests.post(LINE_REPLY_URL, headers=headers, json=body)

def extract_date(text):
    match = re.search(r'(\d{1,2})\s*ก\.?ค\.?\.?\s*(\d{2,4})', text)
    if match:
        day = int(match.group(1))
        year = int(match.group(2))
        year += 2500 if year < 100 else 0
        return datetime(year - 543, 7, day)
    return None

@app.route("/webhook", methods=["POST"])
def webhook():
    payload = request.json
    events = payload.get("events", [])

    for event in events:
        if event["type"] == "message":
            text = event["message"]["text"].strip()
            reply_token = event["replyToken"]

            # ✅ ตรวจสอบคำสั่ง /list
            if text.lower() == "/list":
                with sqlite3.connect("database.db") as conn:
                    cursor = conn.execute("SELECT detail, due_date FROM tasks ORDER BY due_date ASC")
                    rows = cursor.fetchall()

                if not rows:
                    reply_to_line(reply_token, "📂 ไม่มีรายการที่บันทึกไว้")
                else:
                    message = "📋 รายการทั้งหมด:\n"
                    for i, (detail, due_date) in enumerate(rows[:5], start=1):
                        message += f"{i}. ครบกำหนด {due_date}:\n- {detail[:80]}\n\n"
                    if len(rows) > 5:
                        message += f"...และอีก {len(rows)-5} รายการ"
                    reply_to_line(reply_token, message)
                return jsonify({"status": "ok"})

            # ✅ ตรวจสอบข้อความทั่วไป
            due_date = extract_date(text)
            if due_date:
                with sqlite3.connect("database.db") as conn:
                    conn.execute("INSERT INTO tasks (detail, due_date) VALUES (?, ?)",
                                 (text, due_date.strftime("%Y-%m-%d")))

                msg = f"📌 ตรวจพบภารกิจใหม่\nครบกำหนด: {due_date.strftime('%-d %b %Y')}\nระบบจะแจ้งเตือนล่วงหน้า"
                reply_to_line(reply_token, msg)
            elif text.lower() == "/list":
                # (จัดการ /list ด้านบนแล้วใน if แรก)
                pass
            else:
                pass
    
    return jsonify({"status": "ok"})

# --- Run Server ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
