#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import time
import requests
from seleniumbase import SB

BASE_URL = "https://store.9v4.com"

# 优先读取 9v4 专属配置，未配置则复用 KATABUMP 账号配置
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
        f"👤 签到账户: {masked_email}\n"
        f"💰 当前积分: {balance}\n"
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

def handle_turnstile(sb) -> bool:
    print("🔍 检测并处理 Cloudflare Turnstile 验证...")
    _SOLVED_JS = """
    return !!(document.querySelector('input[name="cf-turnstile-response"]')?.value?.length > 20);
    """
    _EXPAND_JS = """
    document.querySelectorAll('iframe').forEach(function(f){
        if (f.src && f.src.includes('challenges.cloudflare.com')) {
            f.style.width = '300px'; f.style.height = '65px';
            f.style.visibility = 'visible'; f.style.opacity = '1';
        }
    });
    """
    time.sleep(3)
    if sb.execute_script(_SOLVED_JS):
        print("✅ Turnstile 已自动静默通过")
        return True

    for attempt in range(6):
        try:
            sb.execute_script(_EXPAND_JS)
        except Exception:
            pass
        if sb.execute_script(_SOLVED_JS):
            print(f"✅ Turnstile 通过（第 {attempt} 次）")
            return True

        print(f"🖱️ 第 {attempt + 1} 次尝试点击 Turnstile 验证框...")
        try:
            sb.uc_gui_click_captcha()
        except Exception as e:
            print(f"⚠️ 点击异常: {e}")

        for _ in range(12):
            time.sleep(0.5)
            if sb.execute_script(_SOLVED_JS):
                print("✅ Turnstile 验证通过！")
                return True
    print("⚠️ Turnstile 未确认通过，尝试继续提交...")
    return False

def login(sb, email, password) -> bool:
    print(f"🌐 打开登录页面: {BASE_URL}/login")
    sb.uc_open_with_reconnect(f"{BASE_URL}/login", reconnect_time=8)
    time.sleep(6)

    # 9v4 的登录输入框 ID 是 #identifier
    print("⏳ 等待登录表单加载...")
    try:
        sb.wait_for_element('#identifier, input[name="identifier"]', timeout=25)
    except Exception:
        print(f"❌ 页面未加载出输入框 (当前 URL: {sb.get_current_url()}, 标题: {sb.get_title()})")
        return False

    print("📧 填写账号与密码...")
    sb.click('#identifier')
    sb.type('#identifier', email)
    time.sleep(1)

    sb.click('#password')
    sb.type('#password', password)
    time.sleep(2)

    # 处理 Turnstile 人机验证
    handle_turnstile(sb)
    time.sleep(1)

    print("🖱️ 点击 Sign in 提交登录...")
    try:
        sb.click('button[type="submit"]')
    except Exception:
        sb.press_keys('#password', '\n')

    print("⏳ 等待跳转至 Dashboard...")
    for _ in range(20):
        time.sleep(1)
        if "dashboard" in sb.get_current_url().lower():
            print("✅ 登录成功，已进入 Dashboard！")
            return True

    print(f"❌ 登录未跳转，当前 URL: {sb.get_current_url()}")
    return False

def get_balance(sb) -> str:
    try:
        bal = sb.execute_script("""
            var spans = document.querySelectorAll('span, div, p, h2, h3');
            for (var i = 0; i < spans.length; i++) {
                var txt = (spans[i].innerText || '').trim();
                if (/^\\d+\\s+credits$/i.test(txt)) {
                    return txt;
                }
            }
            return '';
        """)
        if bal:
            return bal
    except Exception:
        pass
    return "未知"

def do_checkin(sb, email):
    print("🎁 正在加载控制台数据...")
    time.sleep(5)

    before_balance = get_balance(sb)
    print(f"💰 签到前积分: {before_balance}")

    # 查找页面上的 Check in 按钮
    checkin_btn = None
    already_checked = False

    buttons = sb.find_elements("button")
    for btn in buttons:
        txt = (btn.text or "").strip()
        if txt.lower() == "check in":
            checkin_btn = btn
            break
        elif txt.lower() == "view":
            # 如果 Daily check-in 卡片上的按钮变成了 View，说明今天已经签过到了
            already_checked = True

    if not checkin_btn and already_checked:
        print("⏳ 今日已经签到过了（按钮显示为 View）")
        send_tg_message("⏳", "今日已签到", email, before_balance, "明天再来吧")
        return

    if checkin_btn:
        print("🖱️ 第一步：点击面板上的 Check in 按钮打开转盘弹窗...")
        checkin_btn.click()
        time.sleep(3)

        # 在弹出的模态框中查找 "Spin to check in" 按钮
        spin_btn = None
        for btn in sb.find_elements("button"):
            txt = (btn.text or "").strip().lower()
            if "spin to check in" in txt:
                spin_btn = btn
                break
            elif "checked in today" in txt:
                print("⏳ 弹窗显示今日已签到 (Checked in today)")
                send_tg_message("⏳", "今日已签到", email, before_balance)
                return

        if spin_btn:
            print("🎡 第二步：点击 Spin to check in 开始转盘抽奖...")
            spin_btn.click()
            # 源码中转盘旋转动画为 4 秒，4 秒后前端自动调用 /api/wallet/rewards/claim 领取奖励
            print("⏳ 等待 8 秒让转盘动画结束并自动领取积分入账...")
            time.sleep(8)

            # 刷新页面读取最新积分
            sb.refresh()
            time.sleep(5)
            after_balance = get_balance(sb)
            print(f"✅ 签到完成！最新积分: {after_balance}")
            send_tg_message("🎉", "签到成功", email, after_balance, f"签到前: {before_balance} → 签到后: {after_balance}")
            return

    print("ℹ️ 未找到可点击的签到按钮，可能今日已完成签到")
    send_tg_message("⏳", "今日已签到或无需操作", email, before_balance)

def main():
    IS_PROXY = os.environ.get("IS_PROXY", "false").lower() == "true"
    proxy_str = os.environ.get("PROXY_SERVER", "").strip() or "http://127.0.0.1:1081"
    sb_kwargs = {"uc": True, "headless": False}
    if IS_PROXY:
        sb_kwargs["proxy"] = proxy_str

    account_list = []
    if USERS_JSON.strip():
        try:
            account_list = json.loads(USERS_JSON)
        except Exception:
            pass

    if not account_list and EMAIL and PASSWORD:
        account_list = [{"username": EMAIL, "password": PASSWORD}]

    if not account_list:
        print("❌ 未配置账号密码！")
        return

    for acc in account_list:
        u = (acc.get("username") or acc.get("email") or "").strip()
        p = (acc.get("password") or "").strip()
        # 如果账号密码为空，或者包含中文占位提示词，直接跳过不执行
        if not u or not p or "账号" in u or "密码" in p or "example.com" in u:
            continue
        print(f"\n================ 开始处理账户: {u} ================")
        with SB(**sb_kwargs) as sb:
            if login(sb, u, p):
                do_checkin(sb, u)
            else:
                send_tg_message("❌", "登录失败", u)
        time.sleep(3)

if __name__ == "__main__":
    main()
