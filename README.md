## 🚀 多平台自动续期与每日签到（GitHub Actions）

这是一个基于 GitHub Actions 的自动化合集仓库，目前支持以下 4 个平台的定时自动续期 / 每日签到：

| 任务名称 | 对应脚本 | 工作流文件 | 定时时间（北京时间） | 说明 |
| --- | --- | --- | --- | --- |
| **Katabump 自动续期** | `app.py` | `.github/workflows/renew.yml` | 每天 `06:15` | 自动登录 [Katabump](https://dashboard.katabump.com) 并续期服务器 |
| **9v4 每日签到** | `9v4_app.py` | `.github/workflows/9v4_checkin.yml` | 每天 `06:30` | 自动登录 [store.9v4.com](https://store.9v4.com) 每日签到领积分 |
| **1A2X 社区每日签到** | `1a2x_app.py` | `.github/workflows/1a2x_checkin.yml` | 每天 `06:45` | 自动登录 [1a2x.com](https://1a2x.com) 每日签到领香蕉 |
| **FurryBox 每日签到** | `furrybox_app.py` | `.github/workflows/furrybox_checkin.yml` | 每天 `07:00` | 自动登录 [furry.box](https://www.furry.box) 每日签到领 Boxes |

> ⚠️ **关于 Cloudflare 防护**：Katabump、9v4、1A2X 均开启了 Cloudflare 防护，普通机房 IP 可能无法通过人机验证，建议配置干净的代理节点，例如 [B2proxy 住宅代理](https://www.b2proxy.com/signup?code=0F5133)。

---

## 🔐 Secrets 配置说明

前往仓库 **Settings → Secrets and variables → Actions → Repository secrets** 添加以下变量：

### 1. 全局通用配置

| Secret 名称 | 是否必填 | 说明 |
| --- | --- | --- |
| `NODE_LINK` | ❌ 可选 | 代理节点链接（支持 `vless://` `vmess://` `trojan://` `tuic://` `anytls://` `hysteria2://` `socks5://`），不填则直连 |
| `TG_BOT_TOKEN` | ❌ 可选 | Telegram Bot Token（用于发送签到/续期通知） |
| `TG_CHAT_ID` | ❌ 可选 | Telegram Chat ID（接收通知的用户或群组 ID） |

### 2. Katabump 自动续期

| Secret 名称 | 是否必填 | 说明 |
| --- | --- | --- |
| `KATABUMP_EMAIL` | ✅ 必填 | Katabump 登录邮箱（**同时作为 9v4 / 1A2X / FurryBox 的默认复用邮箱**） |
| `KATABUMP_PASSWORD` | ✅ 必填 | Katabump 登录密码（**同时作为 9v4 / 1A2X / FurryBox 的默认复用密码**） |

### 3. 9v4 每日签到（`9v4_app.py`）

> 若 9v4 账号密码与 Katabump 一致，可跳过单独配置，脚本会自动复用 `KATABUMP_EMAIL` / `KATABUMP_PASSWORD`。

| Secret 名称 | 是否必填 | 说明 |
| --- | --- | --- |
| `STORE9V4_EMAIL` | ❌ 可选 | 9v4 登录邮箱（覆盖默认复用邮箱） |
| `STORE9V4_PASSWORD` | ❌ 可选 | 9v4 登录密码（覆盖默认复用密码） |
| `STORE9V4_USERS` | ❌ 可选 | 多账号 JSON 数组，格式：`[{"email":"a@b.com","password":"123"}]` |

### 4. 1A2X 社区每日签到（`1a2x_app.py`）

> 💡 **强烈推荐配置 `FORUM_1A2X_COOKIE`**：勾选“记住我”登录后复制 Cookie，可跳过登录页、Turnstile 人机验证与异地二次验证，有效期长达 180 天。

| Secret 名称 | 是否必填 | 说明 |
| --- | --- | --- |
| `FORUM_1A2X_COOKIE` | ❌ 推荐 | 浏览器登录后的 Cookie 字符串（支持免密直登） |
| `FORUM_1A2X_EMAIL` | ❌ 可选 | 1A2X 登录邮箱（未配 Cookie 且与 Katabump 不同时填写） |
| `FORUM_1A2X_PASSWORD` | ❌ 可选 | 1A2X 登录密码 |
| `FORUM_1A2X_TOTP` | ❌ 可选 | 两步验证（2FA）的 Base32 密钥（仅账号密码登录遇到 `/login/verify` 时需要） |
| `FORUM_1A2X_USERS` | ❌ 可选 | 多账号 JSON 数组，格式：`[{"email":"...","password":"...","cookie":"...","totp":"..."}]` |

### 5. FurryBox 每日签到（`furrybox_app.py`）

> 若 FurryBox 账号密码与 Katabump 一致，无需单独配置，脚本会自动复用 `KATABUMP_EMAIL` / `KATABUMP_PASSWORD`。

| Secret 名称 | 是否必填 | 说明 |
| --- | --- | --- |
| `FURRYBOX_EMAIL` | ❌ 可选 | FurryBox 登录邮箱（覆盖默认复用邮箱） |
| `FURRYBOX_PASSWORD` | ❌ 可选 | FurryBox 登录密码（覆盖默认复用密码） |
| `FURRYBOX_USERS` | ❌ 可选 | 多账号 JSON 数组，格式：`[{"email":"a@b.com","password":"123"}]` |

---

### 🌐 代理格式说明（确认在 v2rayN 里使用正常的节点）

`NODE_LINK` 支持以下任意一种代理协议的完整分享链接（不配置则直连）：

- **VLESS**：`vless://uuid@server:port?security=reality&sni=...&type=ws&...`
- **VMess**：`vmess://base64encoded...`
- **Trojan**：`trojan://password@server:port?sni=...&type=ws&...`
- **tuic**：`tuic://uuid:password@server:port...`
- **anytls**：`anytls://uuid@server:port...`
- **hysteria2**：`hysteria2://base64@server:port...`
- **SOCKS5**：`socks5://user:pass@server:port` 或 `socks://user:pass@server:port`

### 📌 注意事项
- 尽量添加一个干净的节点，以免过不了 Cloudflare 人机验证
- 各工作流的 `cron` 定时时间已按北京时间 `06:15 / 06:30 / 06:45 / 07:00` 错开 15 分钟，避免同时并发触发冲突
- 请确保在仓库 **Settings → Actions → General → Workflow permissions** 中勾选 **Read and write permissions**，以便 `time.txt` 保活提交正常运行
