#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import time
import requests

SUPABASE_URL = "https://pwfcgdrorwpdzatxavdt.supabase.co"
SUPABASE_ANON_KEY = "sb_publishable_KWmBOppH3DRoJf4-g9UCwQ_qLUZojRR"
FUNCTIONS_URL = f"{SUPABASE_URL}/functions/v1"

EMAIL = os.environ.get("FURRYBOX_EMAIL") or os.environ.get("KATABUMP_EMAIL") or ""
PASSWORD = os.environ.get("FURRYBOX_PASSWORD") or os.environ.get("KATABUMP_PASSWORD") or ""
USERS_JSON = os.environ.get("USERS_JSON") or ""
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN") or ""
TG_CHAT_ID = os.environ.get("TG_CHAT_ID") or ""


def send_tg_message(status_icon, status_text, email, balance="未知", detail=""):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("ℹ️ 未配置 TG_BOT_TOKEN 或 TG_CHAT_ID，跳过推送。")
        return

    local_time = time.gmtime(time.time() + 8 * 3600)
    current_time_str = time.strftime("%Y-%m-%d %H:%M:%S", local_time)

    if "@" in email:
        name, domain = email.split("@", 1)
        masked_email = f"{name[:2]}****{name[-2:]}@{domain}" if len(name) > 4 else f"{name}@{domain}"
    else:
        masked_email = email[:2] + "****"

    text = (
        f"📦 FurryBox 每日签到通知\n\n"
        f"{status_icon} {status_text}\n"
        f"👤 签到账户: {masked_email}\n"
        f"💰 当前 Boxes: {balance}\n"
        f"⏱️ 执行时间: {current_time_str}"
    )
    if detail:
        text += f"\n📝 详情: {detail}"

    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TG_CHAT_ID, "text": text}, timeout=10)
        print("📩 Telegram 通知发送成功！")
    except Exception as e:
        print(f"⚠️ Telegram 发送失败: {e}")


def login(session: requests.Session, email: str, password: str) -> str:
    url = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
    headers = {
        "Content-Type": "application/json",
        "apikey": SUPABASE_ANON_KEY,
    }
    resp = session.post(url, headers=headers, json={"email": email, "password": password}, timeout=20)
    data = resp.json() if resp.content else {}
    if not resp.ok or not data.get("access_token"):
        err = data.get("error_description") or data.get("msg") or data.get("error") or f"HTTP {resp.status_code}"
        raise RuntimeError(f"登录失败: {err}")
    return data["access_token"]


def call_auth_action(session: requests.Session, access_token: str, action: str) -> tuple[int, dict]:
    url = f"{FUNCTIONS_URL}/auth"
    headers = {
        "Content-Type": "application/json",
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {access_token}",
    }
    resp = session.post(url, headers=headers, json={"action": action}, timeout=20)
    try:
        data = resp.json()
    except Exception:
        data = {"message": resp.text}
    return resp.status_code, data


def get_wallet_balance(session: requests.Session, access_token: str) -> str:
    status, data = call_auth_action(session, access_token, "wallet")
    if status == 200 and isinstance(data, dict):
        wallet = data.get("wallet") or {}
        if "balance" in wallet:
            return str(wallet["balance"])
    return "未知"


def run_account(email: str, password: str) -> bool:
    print(f"🚀 开始处理 FurryBox 账号: {email}")
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})

    try:
        access_token = login(session, email, password)
        print("✅ 登录成功，正在执行每日签到...")

        status, data = call_auth_action(session, access_token, "signin")
        if 200 <= status < 300:
            amount = data.get("amount", 5)
            balance = data.get("balance")
            if balance is None:
                balance = get_wallet_balance(session, access_token)
            msg = f"签到成功！获得 {amount} boxes"
            print(f"🎉 {msg}，当前余额: {balance}")
            send_tg_message("✅", msg, email, balance=str(balance))
            return True

        err_code = str(data.get("code") or "")
        err_msg = str(data.get("error") or data.get("message") or data.get("msg") or f"HTTP {status}")
        if err_code == "ALREADY_SIGNED_IN" or "ALREADY_SIGNED_IN" in err_msg or "已经签到" in err_msg:
            balance = get_wallet_balance(session, access_token)
            print(f"ℹ️ 今日已签到，当前余额: {balance}")
            send_tg_message("ℹ️", "今日已签到（无需重复领取）", email, balance=str(balance))
            return True

        print(f"❌ 签到失败: {err_msg} (HTTP {status})")
        send_tg_message("❌", "签到失败", email, detail=err_msg)
        return False

    except Exception as e:
        print(f"❌ 执行异常: {e}")
        send_tg_message("❌", "执行异常", email, detail=str(e))
        return False


def main():
    accounts = []
    if USERS_JSON.strip():
        try:
            parsed = json.loads(USERS_JSON)
            if isinstance(parsed, list):
                accounts = [a for a in parsed if a.get("email") and a.get("password")]
        except Exception as e:
            print(f"⚠️ 解析 USERS_JSON 失败: {e}")

    if not accounts and EMAIL and PASSWORD:
        accounts = [{"email": EMAIL, "password": PASSWORD}]

    if not accounts:
        print("❌ 未配置账号！请在 GitHub Secrets 中配置 FURRYBOX_EMAIL / FURRYBOX_PASSWORD（或复用 KATABUMP_EMAIL / KATABUMP_PASSWORD），或配置 FURRYBOX_USERS。")
        raise SystemExit(1)

    all_ok = True
    for acc in accounts:
        ok = run_account(acc["email"], acc["password"])
        if not ok:
            all_ok = False

    if not all_ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
