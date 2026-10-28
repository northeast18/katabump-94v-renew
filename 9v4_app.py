#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import time
import requests
from seleniumbase import SB

BASE_URL = "https://store.9v4.com"

# 优先读取 9v4 专属账号，若未填则复用已有的 KATABUMP 账号
EMAIL = os.environ.get("STORE9V4_EMAIL") or os.environ.get("KATABUMP_EMAIL") or ""
PASSWORD = os.environ.get("STORE9V4_PASSWORD") or os.environ.get("KATABUMP_PASSWORD") or ""
USERS_JSON = os.environ.get("USERS_JSON") or ""
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN") or ""
TG_CHAT_ID = os.environ.get("TG_CHAT_ID") or ""

def send_tg_message(status_icon, status_text, email, balance="未知", detail=""):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("ℹ️ 未配置 TG_BOT_TOKEN 或 TG_CHAT_ID，跳过推送。")
        return

    local_time = time.gmtime(time.time() + 8 * 3600)
    current_time_str = time.strftime("%Y-%m-%d %H:%M:%S", local_time)

    if '@' in email:
        name, domain = email.split('@', 1)
        masked_email = f"{name[:2]}****{name[-2:]}@{domain}" if len(name) > 4 else f"{name}@{domain}"
    else:
        masked_email = email[:2] + '****'

    text = (
        f"🌐 9v4.com 每日签到通知\n\n"
        f"{status_icon} {status_text}\n"
        f"👤 账户: {masked_email}\n"
        f"💰 当前积分: {balance}\n"
        f"⏱️ 时间: {current_time_str}"
    )
    if detail:
        text += f"\n📝 详情: {detail}"

    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TG_CHAT_ID, "text": text}, timeout=10)
        print("📩 Telegram 通知发送成功！")
    except Exception as e:
        print(f"⚠️ Telegram 发送失败: {e}")

def js_fill_input(sb, selector: str, text: str):
    safe_text = text.replace('\\', '\\\\').replace('"', '\\"')
    sb.execute_script(f"""
    (function(){{
        var el = document.querySelector('{selector}');
        if (!el) return;
        var setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
        if (setter) {{ setter.call(el, "{safe_text}"); }} else {{ el.value = "{safe_text}"; }}
        el.dispatchEvent(new Event('input', {{ bubbles: true }}));
        el.dispatchEvent(new Event('change', {{ bubbles: true }}));
    }})()
    """)

def handle_turnstile(sb) -> bool:
    print("🔍 处理 Cloudflare Turnstile 验证...")
    _SOLVED_JS = "return !!(document.querySelector('input[name=\"cf-turnstile-response\"]')?.value?.length > 20);"
    time.sleep(2)
    if sb.execute_script(_SOLVED_JS):
        return True
    for attempt in range(5):
        if sb.execute_script(_SOLVED_JS):
            return True
        try: sb.uc_gui_click_captcha()
        except Exception: pass
        for _ in range(10):
            time.sleep(0.5)
            if sb.execute_script(_SOLVED_JS):
                return True
    return False

def login(sb, email, password) -> bool:
    print(f"🌐 打开登录页面: {BASE_URL}/login")
    sb.uc_open_with_reconnect(f"{BASE_URL}/login", reconnect_time=6)
    time.sleep(6)

    try:
        sb.wait_for_element('input[type="email"], input[name="email"]', timeout=20)
    except Exception:
        print("❌ 页面未加载出输入框")
        return False

    print("📧 填写账号密码...")
    js_fill_input(sb, 'input[type="email"], input[name="email"]', email)
    time.sleep(1)
    js_fill_input(sb, 'input[type="password"], input[name="password"]', password)
    time.sleep(2)

    handle_turnstile(sb)

    print("🖱️ 提交登录...")
    try: sb.click('button[type="submit"]')
    except Exception: sb.press_keys('input[type="password"]', '\n')

    for _ in range(15):
        time.sleep(1)
        if "dashboard" in sb.get_current_url().lower():
            print("✅ 成功进入 Dashboard！")
            return True
    return "dashboard" in sb.get_current_url().lower()

def get_balance(sb) -> str:
    try:
        return sb.execute_script("""
            var cards = document.querySelectorAll('div');
            for (var i = 0; i < cards.length; i++) {
                if ((cards[i].innerText || '').includes('BALANCE')) {
                    var m = cards[i].innerText.match(/(\\d+\\s*(credits|points)?)/i);
                    if (m) return m[0];
                }
            }
            return '未知';
        """)
    except Exception:
        return "未知"

def do_checkin(sb, email):
    print("🎁 执行每日签到...")
    time.sleep(3)

    # 优先使用底层 API 签到
    api_result = sb.execute_script("""
        return (async function() {
            try {
                let res = await fetch('/api/plugins/checkin/spin', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                let data = await res.json();
                return { ok: res.ok, status: res.status, data: data };
            } catch (err) {
                return { error: err.toString() };
            }
        })();
    """)
    print(f"📡 API 结果: {api_result}")

    if api_result and isinstance(api_result, dict):
        if api_result.get("ok"):
            time.sleep(2)
            bal = get_balance(sb)
            msg = api_result.get('data', {}).get('message', '签到成功')
            send_tg_message("🎉", "签到成功", email, bal, msg)
            return
        elif api_result.get("status") in [400, 422, 409]:
            bal = get_balance(sb)
            msg = api_result.get('data', {}).get('message', '今日已签到')
            send_tg_message("⏳", "今日已签到", email, bal, msg)
            return

    # 界面点击兜底
    try:
        for btn in sb.find_elements("button"):
            if "check in" in (btn.text or "").strip().lower():
                btn.click()
                print("✅ 已点击 Check in 按钮")
                break
    except Exception:
        pass

    time.sleep(3)
    bal = get_balance(sb)
    send_tg_message("✅", "已执行签到操作", email, bal)

def main():
    IS_PROXY = os.environ.get("IS_PROXY", "false").lower() == "true"
    proxy_str = os.environ.get("PROXY_SERVER", "").strip() or "http://127.0.0.1:1081"
    sb_kwargs = {"uc": True, "headless": False}
    if IS_PROXY:
        sb_kwargs["proxy"] = proxy_str

    if not EMAIL or not PASSWORD:
        print("❌ 未检测到 9v4 账号密码，请检查 Secrets 配置。")
        return

    with SB(**sb_kwargs) as sb:
        if login(sb, EMAIL, PASSWORD):
            do_checkin(sb, EMAIL)
        else:
            send_tg_message("❌", "登录失败", EMAIL)

if __name__ == "__main__":
    main()
