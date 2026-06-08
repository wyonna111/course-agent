# 线上 Demo 自检清单（成员 A）

部署地址：`________________`（在 Streamlit Cloud → App Settings 查看）

---

## 推送代码后

- [ ] `git push origin main` 成功
- [ ] Streamlit Cloud 显示 **Running**（或自动重新 Deploy 完成）
- [ ] 浏览器打开 demo 地址，页面正常加载

---

## 功能冒烟测试（约 5 分钟）

| # | 操作 | 通过 |
|---|------|------|
| 1 | 左侧上传 1 个 PDF，点击「解析并加入索引」 | ☐ |
| 2 | 右侧提问，能收到回答 | ☐ |
| 3 | 展开「课内参考资料」，有页码与正文 | ☐ |
| 4 | 协作空间 → 创建协作空间，出现邀请码 | ☐ |
| 5 | 分享链接格式为 `https://你的地址/?space=邀请码` | ☐ |

---

## 常见问题

| 现象 | 处理 |
|------|------|
| 页面白屏 / 崩溃 | 查看 Streamlit Cloud Logs；确认 `OPENAI_API_KEY` 已在 Secrets 配置 |
| 402 错误 | API 余额不足，充值或换 Key |
| 协作邀请码无效 | 队友必须打开**同一** `.streamlit.app` 地址，不能各自 localhost |
| Deploy 失败 | 检查 `requirements.txt` 与 Python 3.11 |

---

## 填写到群公告

确认通过后，把 demo 地址填入 `docs/TASKS.md` 群消息模板第一行，再发给 B、C。
