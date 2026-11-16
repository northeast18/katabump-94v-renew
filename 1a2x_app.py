#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import time
import hmac
import base64
import struct
import hashlib
import requests
from seleniumbase import SB

BASE_URL = "https://1a2x.com"

EMAIL = os.environ.get("FORUM_1A2X_EMAIL") or os.environ.get("KATABUMP_EMAIL") or ""
PASSWORD = os.environ.get("FORUM_1A2X_PASSWORD") or os.environ.get("KATABUMP_PASSWORD") or ""
COOKIE_STR = os.environ.get("FORUM_1A2X_COOKIE") or ""
TOTP_SECRET = os.environ.get("FORUM_1A2X_TOTP") or ""
USERS_JSON = os.environ.get("USERS_JSON") or ""
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN") or ""
TG_CHAT_ID = os.environ.get("TG_CHAT_ID") or ""

def generate_totp(secret: str) -> str:
    key = base64.b32decode(secret.strip().replace(" ", "").upper() + "=" * ((8 - len(secret.strip()) % 8) % 8))
    counter = int(time.time()) // 30
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % 1000000
    return f"{code:06d}"

def send_tg_message(status_icon, status_text, account_label, banana_info="未知", detail=""):
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print("ℹ️ 未配置 TG_BOT_TOKEN 或 TG_CHAT_ID，跳过推送。")
        return

    local_time = time.gmtime(time.time() + 8 * 3600)
    current_time_str = time.strftime("%Y-%m-%d %H:%M:%S", local_time)

    if '@' in account_label:
        name, domain = account_label.split('@', 1)
        masked = f"{name[:2]}****{name[-2:]}@{domain}" if len(name) > 4 else f"{name}@{domain}"
    else:
        masked = account_label

    text = (
        f"🍌 1A2X 社区每日签到通知\n\n"
        f"{status_icon} {status_text}\n"
        f"👤 签到账户: {masked}\n"
        f"🍌 香蕉状态: {banana_info}\n"
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
    print("🔍 检测并处理 Cloudflare Turnstile 人机验证...")
    _SOLVED_JS = """
    (() => {
        var el = document.querySelector('#password-login input[name="cf-turnstile-response"]') || document.querySelector('input[name="cf-turnstile-response"]');
        var fb = document.querySelector('#password-login .turnstile-feedback');
        var fb_ok = fb && (fb.innerText.includes('验证通过') || fb.innerText.includes('Verification complete'));
        return !!((el && el.value && el.value.length > 20) || fb_ok);
    })()
    """
    _PREPARE_JS = """
    (() => {
        var w = document.querySelector('#password-login .turnstile-widget');
        if (w) w.scrollIntoView({block: 'center'});
        document.querySelectorAll('#password-login iframe').forEach(function(f){
            if (f.src && f.src.includes('challenges.cloudflare.com')) {
                f.style.width = '300px'; f.style.height = '65px';
                f.style.visibility = 'visible'; f.style.opacity = '1';
            }
        });
    })()
    """
    time.sleep(3)
    if sb.execute_script(_SOLVED_JS):
        print("✅ Turnstile 已自动静默通过")
        return True

    for attempt in range(6):
        try:
            sb.execute_script(_PREPARE_JS)
        except Exception:
            pass
        if sb.execute_script(_SOLVED_JS):
            return True

        print(f"🖱️ 第 {attempt + 1} 次尝试点击 Turnstile 验证框...")
        try:
            sb.uc_gui_click_captcha()
        except Exception:
            pass

        for _ in range(14):
            time.sleep(0.5)
            if sb.execute_script(_SOLVED_JS):
                print("✅ Turnstile 验证通过！")
                return True
    return False

def is_logged_in(sb) -> bool:
    return bool(sb.execute_script("""
    (() => {
        var url = window.location.href;
        if (url.includes('/login')) return false;
        return !!(document.querySelector('.daily-checkin, .welcome-panel-member, form[action*="/logout"]') && !document.querySelector('a.header-login'));
    })()
    """))

def login_with_cookie(sb, cookie_str: str) -> bool:
    print("🍪 检测到 Cookie 配置，尝试免密直登...")
    sb.uc_open_with_reconnect(BASE_URL, reconnect_time=5)
    time.sleep(3)

    added_count = 0
    for item in cookie_str.split(";"):
        if "=" in item:
            k, v = item.strip().split("=", 1)
            k, v = k.strip(), v.strip()
            if k:
                try:
                    sb.driver.add_cookie({"name": k, "value": v, "path": "/"})
                    added_count += 1
                except Exception as e:
                    print(f"⚠️ 注入 Cookie [{k}] 失败: {e}")

    print(f"🍪 共注入 {added_count} 条 Cookie，刷新页面验证登录态...")
    sb.open(BASE_URL)
    time.sleep(4)
    if is_logged_in(sb):
        print("✅ Cookie 免密登录成功！")
        return True
    print("⚠️ Cookie 已失效或无效，回退至账号密码登录...")
    return False

def login(sb, email, password, totp_secret="") -> tuple[bool, str]:
    print(f"🌐 打开 1A2X 登录页面: {BASE_URL}/login")
    sb.uc_open_with_reconnect(f"{BASE_URL}/login", reconnect_time=8)
    time.sleep(5)

    try:
        sb.wait_for_element('#auth-identity', timeout=25)
    except Exception:
        return False, f"页面未加载出输入框 (URL: {sb.get_current_url()})"

    print("📧 填写账号与密码...")
    sb.click('#auth-identity')
    sb.type('#auth-identity', email)
    time.sleep(1)
    sb.click('#auth-password')
    sb.type('#auth-password', password)
    time.sleep(1)

    try:
        sb.execute_script("(() => { var cb = document.getElementById('remember-login'); if(cb && !cb.checked) cb.click(); })()")
    except Exception:
        pass

    if not handle_turnstile(sb):
        return False, "Cloudflare Turnstile 人机验证未通过"
    time.sleep(1)

    print("🖱️ 点击登录按钮提交...")
    try:
        sb.click('#password-login button.primary.auth-submit')
    except Exception:
        sb.execute_script("(() => { document.querySelector('#password-login').submit(); })()")

    print("⏳ 等待登录结果...")
    for _ in range(25):
        time.sleep(1)
        if is_logged_in(sb):
            print("✅ 登录成功！")
            return True, ""

        cur_url = sb.get_current_url()
        if "/login/verify" in cur_url:
            print("🔐 触发二次安全验证页 (/login/verify)！")
            verify_info = sb.execute_script("""
            (() => {
                var h = document.querySelector('h1, h2, .auth-heading');
                var p = document.querySelector('.auth-panel p, .hint');
                var inp = document.querySelector('input[type="text"], input[type="number"], input[name="code"], input[name="otp"]');
                return {
                    title: h ? h.innerText.trim() : '',
                    desc: p ? p.innerText.trim() : '',
                    input_name: inp ? inp.name : ''
                };
            })()
            """)
            print(f"📋 二次验证要求: {verify_info}")

            if totp_secret and verify_info.get("input_name"):
                code = generate_totp(totp_secret)
                print(f"🔑 使用 TOTP 密钥自动填入验证码: {code}")
                inp_sel = f'input[name="{verify_info["input_name"]}"]'
                sb.type(inp_sel, code)
                time.sleep(1)
                sb.click('button[type="submit"], button.primary.auth-submit')
                for _ in range(15):
                    time.sleep(1)
                    if is_logged_in(sb):
                        print("✅ 二次验证通过，登录成功！")
                        return True, ""
                return False, "TOTP 验证码提交后未成功登录"
            else:
                return False, f"触发二次验证 ({verify_info.get('title')} - {verify_info.get('desc')})，建议更新 Cookie 或配置 TOTP 密钥"

        err_text = sb.execute_script("(() => { var e = document.querySelector('[data-auth-error], .alert.danger, .form-error'); return e ? e.innerText.trim() : ''; })()")
        if err_text:
            return False, err_text

    return False, f"未跳转离开登录页 (URL: {sb.get_current_url()})"

def get_member_info(sb) -> str:
    try:
        info = sb.execute_script("""
        (() => {
            var panel = document.querySelector('.welcome-panel-member') || document.body;
            var txt = panel.innerText || '';
            var m = txt.match(/(\\d+\\s*香蕉|香蕉\\s*[:：]?\\s*\\d+)/i);
            if (m) return m[0].replace(/\\s+/g, ' ');
            var dc = document.querySelector('.daily-checkin');
            if (dc) return dc.innerText.replace(/\\s+/g, ' ').trim();
            return '已登录';
        })()
        """)
        if info:
            return info.strip()
    except Exception:
        pass
    return "未知"

def do_checkin(sb, label):
    print("🎁 正在首页查找每日签到区域 (.daily-checkin)...")
    if sb.get_current_url().rstrip('/') != BASE_URL:
        sb.open(BASE_URL)
        time.sleep(4)

    checkin_state = sb.execute_script("""
    (() => {
        var box = document.querySelector('.daily-checkin');
        if (!box) return { found: false };
        var btn = box.querySelector('button, .checkin-button, a.button');
        var hint = box.querySelector('.hint');
        if (!btn) return { found: true, has_btn: false, text: box.innerText.trim() };
        return {
            found: true,
            has_btn: true,
            disabled: !!btn.disabled || btn.classList.contains('disabled') || btn.getAttribute('aria-disabled') === 'true',
            btn_text: (btn.innerText || '').trim(),
            hint_text: hint ? (hint.innerText || '').trim() : ''
        };
    })()
    """)
    print(f"📋 签到组件状态: {checkin_state}")

    if not checkin_state or not checkin_state.get("found"):
        send_tg_message("⚠️", "未找到签到按钮", label, get_member_info(sb))
        return

    btn_text = checkin_state.get("btn_text", "")
    hint_text = checkin_state.get("hint_text", "")

    if checkin_state.get("disabled") or "已签" in btn_text or "checked" in btn_text.lower():
        info = get_member_info(sb)
        detail = f"{btn_text} ({hint_text})".strip(" ()")
        print(f"⏳ 今日已签到: {detail}")
        send_tg_message("⏳", "今日已签到", label, info, detail)
        return

    print(f"🖱️ 点击签到按钮 ({btn_text})...")
    try:
        sb.click('.daily-checkin button, .daily-checkin .checkin-button')
    except Exception:
        sb.execute_script("(() => { var btn = document.querySelector('.daily-checkin button, .daily-checkin .checkin-button'); if (btn) btn.click(); })()")

    time.sleep(5)
    after_state = sb.execute_script("""
    (() => {
        var box = document.querySelector('.daily-checkin');
        var flash = document.querySelector('.flash, .notice, .toast, [role="alert"], [role="status"]');
        return {
            box_text: box ? box.innerText.replace(/\\s+/g, ' ').trim() : '',
            flash_text: flash ? flash.innerText.replace(/\\s+/g, ' ').trim() : ''
        };
    })()
    """)
    info = get_member_info(sb)
    detail = (after_state.get("flash_text") or after_state.get("box_text") or "已完成签到点击").strip()
    print(f"✅ 签到完成！状态: {info} | 详情: {detail}")
    send_tg_message("🎉", "签到成功", label, info, detail)

def main():
    IS_PROXY = os.environ.get("IS_PROXY", "false").lower() == "true"
    proxy_str = os.environ.get("PROXY_SERVER", "").strip() or "http://127.0.0.1:1081"
    sb_kwargs = {"uc": True, "headless": False}
    if IS_PROXY:
        sb_kwargs["proxy"] = proxy_str

    if COOKIE_STR.strip() and not USERS_JSON.strip():
        with SB(**sb_kwargs) as sb:
            if login_with_cookie(sb, COOKIE_STR):
                do_checkin(sb, EMAIL or "Cookie用户")
                return
            elif EMAIL and PASSWORD:
                ok, err = login(sb, EMAIL, PASSWORD, TOTP_SECRET)
                if ok:
                    do_checkin(sb, EMAIL)
                else:
                    send_tg_message("❌", "登录失败", EMAIL, detail=err)
                return

    account_list = []
    if USERS_JSON.strip():
        try:
            account_list = json.loads(USERS_JSON)
        except Exception:
            pass

    if not account_list and EMAIL and PASSWORD:
        account_list = [{"username": EMAIL, "password": PASSWORD, "totp": TOTP_SECRET}]

    if not account_list:
        print("❌ 未配置账号密码或 Cookie！")
        return

    for acc in account_list:
        u = (acc.get("username") or acc.get("email") or "").strip()
        p = (acc.get("password") or "").strip()
        c = (acc.get("cookie") or "").strip()
        t = (acc.get("totp") or "").strip()
        if (not u or not p) and not c:
            continue
        if "账号" in u or "example.com" in u:
            continue

        print(f"\n================ 开始处理 1A2X 账户: {u or 'Cookie用户'} ================")
        with SB(**sb_kwargs) as sb:
            logged = False
            err = ""
            if c:
                logged = login_with_cookie(sb, c)
            if not logged and u and p:
                logged, err = login(sb, u, p, t)

            if logged:
                do_checkin(sb, u or "Cookie用户")
            else:
                send_tg_message("❌", "登录失败", u or "Cookie用户", detail=err)
        time.sleep(3)

if __name__ == "__main__":
    main()
