# 小组任务分工与截止说明

> **发给 B、C 的群公告**：可直接复制下方「群消息模板」发到微信群。

---

## 群消息模板（复制发送）

```
【课内有据 · 小组任务】

线上 demo：（填写你的 Streamlit 地址，例如 https://xxx.streamlit.app）
仓库：https://github.com/wyonna111/course-agent

成员 A 已完成系统开发与部署，接下来请 B、C 按分工交付，截止时间如下。

━━ 成员 B · 论文与汇报 ━━
截止：答辩前 3 天交 PPT 终稿，第 1 周交初稿

1. 填写 docs/report.md（需求、架构、技术说明）
2. 完善 docs/architecture.md 中的架构图（可导出 PNG 放到 docs/）
3. 用 eval/test_cases.md 里的题目做对比实验，结果填入 docs/report.md 第四节
4. 按 docs/demo-script.md 准备 5 分钟答辩演示
5. 制作答辩 PPT（15～20 页），答辩时由 B 主讲背景与实验

━━ 成员 C · 资料与评测 ━━
截止：第 7 天前完成评测表

1. 整理课件清单 → eval/materials.md（只写文件名，勿上传完整课件到 GitHub）
2. 编写至少 20 道测试题 → eval/test_cases.md
3. 在 demo 上逐题测试，记录结果 → eval/results.md（附截图到 eval/screenshots/）
4. 完成 1～2 个纠错样例（截图前后对比，写在 eval/results.md）
5. 与 B 一起测协作空间 → eval/collab_test.md

有问题在群里 @A，或开 GitHub Issue。

提交方式：把写好的 md 文件 push 到仓库对应目录，或发给 A 代传。
```

---

## 成员 B 任务清单

| # | 任务 | 交付文件 | 截止 |
|---|------|----------|------|
| B1 | 需求与背景分析 | `docs/report.md` 第一、二节 | 第 5 天 |
| B2 | 系统架构图 | `docs/architecture.md` + 可选 `docs/architecture.png` | 第 5 天 |
| B3 | 技术路线说明 | `docs/report.md` 第三节 | 第 7 天 |
| B4 | 对比实验（纯 LLM vs 课内有据） | `docs/report.md` 第四节 | 第 10 天 |
| B5 | 答辩 PPT | 课程提交渠道 / 发给全组 | 答辩前 3 天 |
| B6 | 演示脚本与彩排 | `docs/demo-script.md` | 答辩前 2 天 |

### B 的工作方式

1. Clone 仓库，阅读 `README.md` 了解功能。
2. 打开线上 demo，按 `docs/demo-script.md` 走一遍流程。
3. 等 C 写好 `eval/test_cases.md` 后，选 10 题做对比实验。
4. 实验对比方法：
   - **对照组**：同一问题直接问 DeepSeek（网页或 API），不喂课件。
   - **实验组**：在课内有据上传资料后提问，看回答与页码引用。
   - 记录：是否胡编、是否有页码、内容是否与课件一致。

---

## 成员 C 任务清单

| # | 任务 | 交付文件 | 截止 |
|---|------|----------|------|
| C1 | 课件资料清单 | `eval/materials.md` | 第 3 天 |
| C2 | 测试问题集（≥20 题） | `eval/test_cases.md` | 第 5 天 |
| C3 | 评测结果与截图 | `eval/results.md` + `eval/screenshots/` | 第 7 天 |
| C4 | 纠错功能样例 | `eval/results.md` 纠错章节 | 第 7 天 |
| C5 | 协作空间联调 | `eval/collab_test.md`（与 B 一起） | 第 7 天 |
| C6 | Bug 反馈 | GitHub Issue 或 `eval/results.md` 问题汇总 | 持续 |

### C 的工作方式

1. 从嵌入式等课程课件中挑 2～3 份代表性 PDF/PPT（本地使用，**不要** push 到公开仓库）。
2. 在 demo 左侧「资料库」上传并点击「解析并加入索引」。
3. 按 `eval/test_cases.md` 模板逐题提问，在 `eval/results.md` 填结果。
4. 找 1 页课件有错字或表述问题，用「纠错此页课件」功能修正，截图对比。
5. 创建协作空间，把邀请码发给 B，两人同时提问，测「同步消息」是否正常。

---

## 答辩分工建议

| 成员 | 答辩负责内容 | 时长 |
|------|-------------|------|
| A | 现场 demo + 技术问答（检索、重排、协作实现） | ~3 分钟 |
| B | 背景、架构图、对比实验、项目价值 | ~3 分钟 |
| C | 测试设计、好/坏案例、纠错与协作实测 | ~2 分钟 |
| 共同 | Q&A | 剩余时间 |

---

## 文件目录说明

```
docs/
├── TASKS.md           # 本文件（任务说明）
├── report.md          # B 填写：课程报告
├── architecture.md    # B 填写：架构说明与 Mermaid 图
└── demo-script.md     # B 填写：答辩演示脚本

eval/
├── materials.md       # C 填写：课件清单
├── test_cases.md      # C 填写：测试问题集
├── results.md         # C 填写：评测结果
├── collab_test.md     # C + B：协作空间测试记录
└── screenshots/       # C 放：评测截图（.gitkeep）
```
