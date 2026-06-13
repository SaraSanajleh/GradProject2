#!/usr/bin/env python3
"""
استدعاء إرسال التذكيرات يومياً (قبل الموعد بيومين).
يُشغّل من Task Scheduler على Windows أو يدوياً.
يُرسل POST إلى السيرفر المحلي ثم يكتب النتيجة في log.
"""
from __future__ import annotations

import json
import sys
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

# عنوان السيرفر المحلي (غيّره إذا استخدمت منفذاً أو host مختلفاً)
BASE_URL = "http://127.0.0.1:8000"
DAYS_AHEAD = 2

LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_FILE = LOG_DIR / "reminder_send.log"


def log(msg: str) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    line = f"[{datetime.now().isoformat()}] {msg}\n"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line)
    print(line.strip())


def main() -> int:
    url = f"{BASE_URL}/reminder/send-due?days_ahead={DAYS_AHEAD}"
    try:
        req = urllib.request.Request(url, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            log(f"OK status={resp.status}")
            try:
                data = json.loads(body)
                total = data.get("total_due", 0)
                sent = data.get("emails_sent", 0)
                smtp = data.get("smtp_configured", False)
                due_date = data.get("due_date", "")
                log(f"  تاريخ المواعيد المستحقة: {due_date} | عدد المستحقة: {total} | إيميلات أُرسلت: {sent} | SMTP مضبوط: {smtp}")
                if total > 0 and sent == 0 and not smtp:
                    log("  تحذير: في مواعيد مستحقة لكن SMTP غير مضبوط فما انبعث إيميل.")
                elif total > 0 and sent > 0:
                    log("  تم إرسال التذكيرات بنجاح.")
            except Exception:
                log(f"  body={body}")
            return 0
    except urllib.error.URLError as e:
        log(f"FAIL (السيرفر قد يكون متوقفاً): {e}")
        return 1
    except Exception as e:
        log(f"FAIL {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
