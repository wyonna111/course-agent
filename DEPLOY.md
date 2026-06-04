# 部署到公网（Streamlit Community Cloud）

让队友**只开浏览器**就能用协作空间，需要先把项目部署到一个**大家都能访问的网址**。

推荐方案：**[Streamlit Community Cloud](https://streamlit.io/cloud)**（免费，适合课程 demo）。

---

## 一、准备 GitHub 仓库

在项目根目录 `course-agent` 下执行（需已安装 [Git](https://git-scm.com/) 并登录 GitHub）：

```bash
cd course-agent

git init
git add .
git commit -m "准备 Streamlit Cloud 部署"

# 在 GitHub 网页新建空仓库，不要勾选 README
git branch -M main
git remote add origin https://github.com/<你的用户名>/<仓库名>.git
git push -u origin main
```

**注意：** `.env`、`data/`、`workspaces/` 已在 `.gitignore` 里，不会上传密钥和本地资料。

---

## 二、在 Streamlit Cloud 创建应用

1. 打开 [share.streamlit.io](https://share.streamlit.io)，用 GitHub 登录  
2. 点击 **New app**  
3. 选择刚推送的仓库  
4. **Main file path** 填：`app.py`  
5. **App URL** 可自定义，例如 `course-trace` → 地址为 `https://course-trace.streamlit.app`  
6. 先点 **Advanced settings**，Python 版本选 **3.11**（与 `.python-version` 一致）  
7. 在 **Secrets** 里粘贴（把密钥换成你的）：

```toml
OPENAI_API_KEY = "sk-xxxxxxxx"
OPENAI_API_BASE = "https://api.deepseek.com/v1"
MODEL_NAME = "deepseek-chat"

ENABLE_WEB_SEARCH = "true"
ENABLE_CORRECTIONS = "true"
ENABLE_WORKSPACE = "true"
ENABLE_LLM_RERANK = "true"
ENABLE_REFERENCES = "true"

PUBLIC_APP_URL = "https://course-trace.streamlit.app"
```

`PUBLIC_APP_URL` 填你实际的 App 地址（**不要**末尾 `/`），协作页会自动生成可复制的分享链接。

8. 点击 **Deploy**，等待 2～5 分钟构建完成。

---

## 三、部署后你要做的

1. 打开线上地址，左侧 **👥 协作 → 创建空间**，得到 6 位邀请码  
2. 在协作空间的 **📁 资料库** 上传 PDF/PPT，点 **解析并加入索引**（线上资料与个人电脑 `data/` 无关，需重新上传）  
3. 把协作页里的 **分享链接** 发给队友，例如：

   `https://course-trace.streamlit.app/?space=ABC123`

---

## 四、队友怎么用

1. 浏览器打开你发的链接（或打开首页 → **协作 → 加入空间** → 输入邀请码）  
2. 可选填昵称  
3. 提问前确认左侧已显示「已索引」；需要看最新对话时点 **🔄 同步消息**

**不需要**安装 Python、不需要代码。

---

## 五、重要限制（Streamlit 免费版）

| 项目 | 说明 |
|------|------|
| 资料与对话存储 | 在云端服务器磁盘；**长时间不用可能休眠**，重新唤醒后一般仍在 |
| 重新 Deploy | 若你在 GitHub 更新代码并触发重新部署，**上传的 PDF 和协作空间可能被清空** |
| API 费用 | 问答消耗的是你 Secrets 里的 **DeepSeek API Key** 余额，队友不用各自申请 |

若需要长期稳定保存课件，可考虑学校服务器 + 持久磁盘，或 Render/Fly.io 挂载 Volume（配置更复杂）。

---

## 六、常见问题

**构建失败 / ModuleNotFoundError**  
→ 检查 `requirements.txt` 是否已提交；在 Cloud 日志里看具体缺哪个包。

**打开页面报 API Key 错误**  
→ 在 App → Settings → Secrets 检查 `OPENAI_API_KEY`，保存后 **Reboot app**。

**队友输入邀请码提示不存在**  
→ 邀请码只在**同一套线上环境**有效；确认队友打开的是你的 `.streamlit.app` 链接，不是 `localhost`。

**本地开发**  
→ 仍用 `.env`；也可复制 `.streamlit/secrets.toml.example` 为 `secrets.toml` 做本地测试（勿提交）。

---

## 七、备选：局域网临时演示（不部署）

若仅同一 WiFi 下演示、不上公网：

```powershell
streamlit run app.py --server.address 0.0.0.0
```

将 `http://<主机局域网IP>:8501/?space=<邀请码>` 发给同网队友（主机需保持运行并放行 8501 端口）。
