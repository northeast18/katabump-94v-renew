#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import time
import requests
from seleniumbase import SB

BASE_URL = "https://1a2x.com"

EMAIL = os.environ.get("FORUM_1A2X_EMAIL") or os.environ.get("KATABUMP_EMAIL") or ""
PASSWORD = os.environ.get("FORUM_1A2X_PASSWORD") or os.environ.get("KATABUMP_PASSWORD") or ""
USERS_JSON = os.environ.get("USERS_JSON") or ""
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN") or ""
TG_CHAT_ID = os.environ.get("TG_CHAT_ID") or ""

def send_tg_message(status_icon, status_text, email, banana_info="未知", detail=""):
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
        f"🍌 1A2X 社区每日签到通知\n\n"
        f"{status_icon} {status_text}\n"
        f"👤 签到账户: {masked_email}\n"
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
    var el = document.querySelector('#password-login input[name="cf-turnstile-response"]') || document.querySelector('input[name="cf-turnstile-response"]');
    var fb = document.querySelector('#password-login .turnstile-feedback');
    var fb_ok = fb && (fb.innerText.includes('验证通过') || fb.innerText.includes('Verification complete'));
    return !!((el && el.value && el.value.length > 20) || fb_ok);
    """
    _PREPARE_JS = """
    var w = document.querySelector('#password-login .turnstile-widget');
    if (w) w.scrollIntoView({block: 'center'});
    document.querySelectorAll('#password-login iframe').forEach(function(f){
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
            sb.execute_script(_PREPARE_JS)
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

        for _ in range(14):
            time.sleep(0.5)
            if sb.execute_script(_SOLVED_JS):
                print("✅ Turnstile 验证通过！")
                return True

    fb_text = sb.execute_script("var fb = document.querySelector('#password-login .turnstile-feedback'); return fb ? fb.innerText : '';")
    print(f"❌ Turnstile 6次均未通过 (页面提示: {fb_text})")
    return False

def login(sb, email, password) -> tuple[bool, str]:
    print(f"🌐 打开 1A2X 登录页面: {BASE_URL}/login")
    sb.uc_open_with_reconnect(f"{BASE_URL}/login", reconnect_time=8)
    time.sleep(5)

    print("⏳ 等待登录表单加载...")
    try:
        sb.wait_for_element('#auth-identity', timeout=25)
    except Exception:
        msg = f"页面未加载出输入框 (URL: {sb.get_current_url()}, 标题: {sb.get_title()})"
        print(f"❌ {msg}")
        return False, msg

    print("📧 填写账号与密码...")
    sb.click('#auth-identity')
    sb.type('#auth-identity', email)
    time.sleep(1)

    sb.click('#auth-password')
    sb.type('#auth-password', password)
    time.sleep(1)

    # 勾选记住登录
    try:
        sb.execute_script("var cb = document.getElementById('remember-login'); if(cb && !cb.checked) cb.click();")
    except Exception:
        pass

    # 必须确认 Turnstile 通过后再提交
    if not handle_turnstile(sb):
        return False, "Cloudflare Turnstile 人机验证未通过"
    time.sleep(1)

    print("🖱️ 点击登录按钮提交...")
    try:
        sb.click('#password-login button.primary.auth-submit')
    except Exception:
        sb.execute_script("document.querySelector('#password-login').submit();")

    print("⏳ 等待登录跳转与身份确认...")
    for _ in range(25):
        time.sleep(1)
        state = sb.execute_script("""
            var url = window.location.href;
            var err = document.querySelector('[data-auth-error], .alert.danger, .form-error, .auth-error');
            var fb = document.querySelector('#password-login .turnstile-feedback');
            var loggedIn = !url.includes('/login') && !!(
                document.querySelector('.daily-checkin, .welcome-panel-member, form[action*="/logout"]')
                && !document.querySelector('a.header-login')
            );
            return {
                url: url,
                loggedIn: loggedIn,
                errText: err ? err.innerText.trim() : '',
                fbText: fb ? fb.innerText.trim() : ''
            };
        """)
        if state.get("loggedIn"):
            print(f"✅ 登录成功！当前页面: {state.get('url')}")
            return True, ""
        if state.get("errText"):
            print(f"❌ 登录被拒绝，页面提示: {state.get('errText')}")
            return False, state.get("errText")

    err_detail = f"未跳转离开登录页 (URL: {sb.get_current_url()})"
    print(f"❌ {err_detail}")
    return False, err_detail

def get_member_info(sb) -> str:
    try:
        info = sb.execute_script("""
            var panel = document.querySelector('.welcome-panel-member') || document.body;
            var txt = panel.innerText || '';
            var m = txt.match(/(\\d+\\s*香蕉|香蕉\\s*[:：]?\\s*\\d+)/i);
            if (m) return m[0].replace(/\\s+/g, ' ');
            var dc = document.querySelector('.daily-checkin');
            if (dc) return dc.innerText.replace(/\\s+/g, ' ').trim();
            return '已登录';
        """)
        if info:
            return info.strip()
    except Exception:
        pass
    return "未知"

def do_checkin(sb, email):
    print("🎁 正在首页查找每日签到区域 (.daily-checkin)...")
    if '/login' in sb.get_current_url():
        sb.open(BASE_URL)
        time.sleep(4)

    checkin_state = sb.execute_script("""
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
    """)
    print(f"📋 签到组件状态: {checkin_state}")

    if not checkin_state or not checkin_state.get("found"):
        info = get_member_info(sb)
        print("⚠️ 页面未找到 .daily-checkin 区域")
        send_tg_message("⚠️", "未找到签到按钮", email, info)
        return

    btn_text = checkin_state.get("btn_text", "")
    hint_text = checkin_state.get("hint_text", "")

    if checkin_state.get("disabled") or "已签" in btn_text or "checked" in btn_text.lower():
        info = get_member_info(sb)
        detail = f"{btn_text} ({hint_text})".strip(" ()")
        print(f"⏳ 今日已签到: {detail}")
        send_tg_message("⏳", "今日已签到", email, info, detail)
        return

    print(f"🖱️ 点击签到按钮 ({btn_text})...")
    try:
        sb.click('.daily-checkin button, .daily-checkin .checkin-button')
    except Exception:
        sb.execute_script("""
            var btn = document.querySelector('.daily-checkin button, .daily-checkin .checkin-button');
            if (btn) btn.click();
        """)

    time.sleep(5)

    after_state = sb.execute_script("""
        var box = document.querySelector('.daily-checkin');
        var flash = document.querySelector('.flash, .notice, .toast, [role="alert"], [role="status"]');
        return {
            box_text: box ? box.innerText.replace(/\\s+/g, ' ').trim() : '',
            flash_text: flash ? flash.innerText.replace(/\\s+/g, ' ').trim() : ''
        };
    """)
    info = get_member_info(sb)
    detail = (after_state.get("flash_text") or after_state.get("box_text") or "已完成签到点击").strip()
    print(f"✅ 签到完成！状态: {info} | 详情: {detail}")
    send_tg_message("🎉", "签到成功", email, info, detail)

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
        if not u or not p or "账号" in u or "密码" in p or "example.com" in u:
            continue
        print(f"\n================ 开始处理 1A2X 账户: {u} ================")
        with SB(**sb_kwargs) as sb:
            ok, err = login(sb, u, p)
            if ok:
                do_checkin(sb, u)
            else:
                send_tg_message("❌", "登录失败", u, detail=err)
        time.sleep(3)

if __name__ == "__main__":
    main()
