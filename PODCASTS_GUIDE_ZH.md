# 播客（Podcasts）功能使用指南（中文）

> 适用：`my-notebook` 当前版本（前端 `/podcasts` + 后端 `/api/podcasts/*`）

## 1. 前置条件

1. 确保你已登录账号（`/login`）。
2. 打开 **AI Settings**，确认默认 **provider / model** 可用（用于生成大纲与逐字稿）。
3. **音频（TTS）**：至少配置其一：
   - **`OPENAI_API_KEY`**：使用 OpenAI TTS（如 `tts-1`）。
   - 或未设置 OpenAI Key 时配置 **`GOOGLE_API_KEY`**：后端会走 Google TTS（如 `gemini-2.5-flash-preview-tts`）。
4. **Speaker Profile**：说话人需带有效 **`voice_id`**（与 Esperanto / Google TTS 一致，例如 **`achernar`**）。若只有 Host 占位，请在 Profiles 里编辑 speakers JSON，为每位说话人填写 `voice_id`。

## 2. API 进程（重要）

- **`run_api.py` 默认已关闭 `reload`**，只跑**一个** worker，避免多进程抢端口或跑到旧代码。
- 开发若要热重载：设置环境变量 **`UVICORN_RELOAD=true`** 再启动（会多一个父进程，播客调试时建议关掉）。
- 若 **`completed` 很快且没有 `audio_file`**、大纲仍是旧格式：多半是机器上仍有**多个**监听 **5055** 的旧进程。请在本机关闭多余 `python run_api.py` / `uvicorn`，只保留**一个** API 再试。
- 完整链路（大纲 + 转录 + 多段 TTS + 合并）通常需要 **数分钟**，请耐心等待并在 Episodes 列表刷新查看状态。

## 3. `/podcasts` 页面结构

`/podcasts` 页面包含两个 Tab：

1. **Episodes**：查看并生成播客 episode。
2. **Profiles**：创建和管理 **Episode Profile** 与 **Speaker Profile**。

## 4. 创建 Speaker Profile（说话人配置）

在 **Profiles** Tab 下方找到 **Speaker Profiles**：

1. 填写 **Name**（必填）。
2. **Voice Model (optional)**：可填 `google:gemini-2.5-flash-preview-tts` 或留空（无 OpenAI Key 时会自动用 Google 模型）。
3. **Description (optional)**。
4. 确保 **speakers** 里每位说话人有 **`voice_id`**（Google TTS 可用如 `achernar`）。
5. 点击 **Create Speaker Profile**。

## 5. 创建 Episode Profile（播客节目配置）

在 **Episode Profiles** 区域：

1. **Name**（必填）。
2. **Num Segments**：段数越多 TTS 越久（建议测试时用 **3**）。
3. **Speaker Config**：需与 **Speaker Profile 的 Name** 一致（或与后端配置的 speaker 名一致），否则无法匹配 TTS 声线。
4. **Default Briefing**（可选）。
5. 点击 **Create Episode Profile**。

## 6. 生成 Episode

在 **Episodes** Tab：

1. **Episode Name**、**Episode Profile**、**Speaker Profile** 必选。
2. 可选 **Notebook** 作为素材上下文。
3. 点击 **Generate**。状态会经 `pending` → `processing` → `completed` 或 `failed`。

## 7. 播放（Play）

当 episode 存在 **`audio_file`** 时，前端 **Play** 会打开：

`GET /api/podcasts/episodes/{episode_id}/audio`

需携带登录 Cookie（同站打开即可）。

## 8. 删除、状态说明

- **Delete**：卡片上垃圾桶删除 episode 或 profile。
- **failed**：查看 **`error_message`**；若未生成音频，日志中会有 `podcast create_podcast finished` 与 `result_keys` 便于排查。

## 9. 常见问题

| 现象 | 处理 |
|------|------|
| 很快 `completed` 且无音频 | 清掉多余 5055 进程，单实例启动 API；看日志是否出现 `create_podcast finished`。 |
| OpenAI TTS 报 Key 错误 | 配置 **`OPENAI_API_KEY`**，或只用 **`GOOGLE_API_KEY`** 走 Google TTS。 |
| 一直 `processing` | 查看后端日志；TTS 段数多时会较久。 |
