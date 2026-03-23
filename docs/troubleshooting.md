# 排障手册

## 启动前检查

- AstrBot 已启动且插件已加载
- `port`/`http_port` 未被占用
- 前端 `wsUrl`/`baseUrl` 与后端配置一致
- `ffmpeg` 可在命令行直接调用
- 相关 STT/TTS/聊天 Provider 可用

## 常见问题

### 前端连接失败

检查项：

- 是否出现监听日志：`ws://<host>:<port>` 与 `http://<host>:<http_port>`
- 是否存在端口冲突或防火墙拦截
- 是否已经有另一客户端占用连接（当前单客户端）

### 模型切换不生效

检查项：

- `live2d_model_name` 是否存在于 `live2ds/model_dict.json`
- 日志中是否出现新的 `set-model-and-conf`
- 前端是否处于旧会话状态（可重连）

### 表情或动作不生效

检查项：

- `expression_provider_id` 是否正确且 Provider 可用
- 当前模型是否配置 `emotionMap`/`motionMap`
- 若使用 `motion_id`，是否存在对应 `motion_catalog.json` 或可匹配条目

### 没有音频输出

检查项：

- TTS Provider 是否启用且可用
- `ffmpeg` 是否可用
- 插件数据目录 `cache/audio/` 是否生成 wav 文件

### 麦克风输入无反应

检查项：

- `stt_provider_id` 是否正确
- 前端是否发送 `mic-audio-data` / `mic-audio-end`
- 若使用 `raw-audio-data`，`silero-vad` 是否安装正常

## 建议关注的日志来源

- `astrbot_plugin_self_open_llm_vtuber.platform_adapter`
- `astrbot_plugin_self_open_llm_vtuber.static_resources`
- `astrbot_plugin_self_open_llm_vtuber.adapter`
- 当前使用的 STT/TTS/聊天 Provider 日志
