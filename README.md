# astrbot_plugin_self_open_llm_vtuber

`astrbot_plugin_self_open_llm_vtuber` 是一个给 AstrBot 使用的桌宠式 Live2D 适配插件。

它的作用是把 AstrBot 的文本、语音、表情结果转发给前端 Live2D 页面或 Electron 客户端，让角色可以：

- 通过 WebSocket 与 AstrBot 对话
- 播放 TTS 音频并驱动口型
- 切换 Live2D 模型
- 根据回复内容选择基础表情
- 在无音频回复时也应用表情动作

当前插件目录位于：

`C:\Users\Administrator\Downloads\AstrBot\data\plugins\astrbot_plugin_self_open_llm_vtuber`

当前前端项目目录位于：

`C:\Users\Administrator\Downloads\weather-query\astrbot_plugin_self_open_llm_vtuber_web`

## 功能概览

- AstrBot 平台适配器，平台 ID 为 `olv_pet_adapter`
- WebSocket 服务，默认监听 `ws://127.0.0.1:12396`
- 静态资源服务，默认监听 `http://127.0.0.1:12397`
- 支持 Live2D 模型热切换
- 支持 STT 语音转文本
- 支持基于聊天模型的基础表情规划
- 支持本地音频缓存并通过 HTTP 提供播放地址

## 目录说明

- [main.py](/c:/Users/Administrator/Downloads/AstrBot/data/plugins/astrbot_plugin_self_open_llm_vtuber/main.py)
  插件入口，负责注册平台适配器并注入运行时上下文。
- [platform_adapter.py](/c:/Users/Administrator/Downloads/AstrBot/data/plugins/astrbot_plugin_self_open_llm_vtuber/platform_adapter.py)
  核心适配器，负责 WebSocket、静态资源、音频、表情和消息收发。
- [live2ds](/c:/Users/Administrator/Downloads/AstrBot/data/plugins/astrbot_plugin_self_open_llm_vtuber/live2ds)
  Live2D 模型资源目录。
- [adapter](/c:/Users/Administrator/Downloads/AstrBot/data/plugins/astrbot_plugin_self_open_llm_vtuber/adapter)
  表情规划、协议处理、运行时配置等辅助模块。
- [static_resources.py](/c:/Users/Administrator/Downloads/AstrBot/data/plugins/astrbot_plugin_self_open_llm_vtuber/static_resources.py)
  静态文件 HTTP 服务。
- [_conf_schema.json](/c:/Users/Administrator/Downloads/AstrBot/data/plugins/astrbot_plugin_self_open_llm_vtuber/_conf_schema.json)
  插件配置项定义。

## 环境要求

- 已安装并可运行的 AstrBot
- Python 3.11 或 3.12
- 前端项目 `astrbot_plugin_self_open_llm_vtuber_web`
- 至少一个可用的 TTS / STT / 聊天模型 Provider

推荐准备：

- 一个 STT Provider，用于麦克风输入转文字
- 一个聊天模型 Provider，用于基础表情判断
- 一个 TTS 能力可用的 AstrBot 对话链路，用于生成音频回复

## 安装方式

### 1. 放置插件目录

将本项目放入 AstrBot 插件目录：

`AstrBot/data/plugins/astrbot_plugin_self_open_llm_vtuber`

如果目录已经存在，直接使用当前目录即可。

### 2. 安装插件依赖

本插件依赖的 Python 包主要包括：

- `websockets`
- `pydub`
- `numpy`

如果你的 AstrBot 主环境里还没有这些包，可以在 AstrBot 所用 Python 环境中安装：

```powershell
pip install websockets pydub numpy
```

如果使用本目录下虚拟环境，也可以先激活再安装。

### 3. 准备 ffmpeg

`pydub` 在处理音频格式时通常依赖 `ffmpeg`。如果你发现音频缓存转换失败，请先安装并确保 `ffmpeg` 已加入系统 PATH。

### 4. 准备前端项目

前端项目位于：

`C:\Users\Administrator\Downloads\weather-query\astrbot_plugin_self_open_llm_vtuber_web`

首次使用时执行：

```powershell
npm install
```

开发模式启动：

```powershell
npm run dev
```

如果你只想启动 Web 页面调试，也可以使用：

```powershell
npm run dev:web
```

## AstrBot 侧配置

插件主要配置文件通常位于：

[astrbot_plugin_self_open_llm_vtuber_config.json](/c:/Users/Administrator/Downloads/AstrBot/data/config/astrbot_plugin_self_open_llm_vtuber_config.json)

当前支持的主要配置项如下。

### persona_id

- 含义：启动时使用的人格名称
- 留空：使用 AstrBot 当前默认人格

### chat_buffer_size

- 含义：缓存最近多少条用户 / 助手文本
- 用途：提供给表情规划模型作为最近上下文

### live2d_model_name

- 含义：指定启动时加载的 Live2D 模型名称
- 当前可选值：
  - `mao_pro`
  - `Mk6_1.0`

### stt_provider_id

- 含义：优先使用的语音识别 Provider
- 例如：`whisper`

### expression_provider_id

- 含义：用于基础表情规划的聊天模型 Provider
- 建议使用稳定、遵循指令能力较好的模型
- 例如：`volcengine_ark/GLM-4.7`

### vad_model

- 含义：原始音频断句所用的 VAD 模型
- 当前默认：`silero_vad`

### vad_* 参数

- `vad_prob_threshold`
- `vad_db_threshold`
- `vad_required_hits`
- `vad_required_misses`
- `vad_smoothing_window`

这些参数用于控制麦克风原始音频断句灵敏度。

## 平台适配器配置

平台适配器在 [platform_adapter.py](/c:/Users/Administrator/Downloads/AstrBot/data/plugins/astrbot_plugin_self_open_llm_vtuber/platform_adapter.py) 中注册，默认值如下：

- `host`: `127.0.0.1`
- `port`: `12396`
- `http_port`: `12397`
- `conf_name`: `AstrBot Desktop`
- `conf_uid`: `astrbot-desktop`
- `speaker_name`: `AstrBot`
- `auto_start_mic`: `true`

对应说明：

- `port` 用于前端 WebSocket 连接
- `http_port` 用于前端拉取模型、背景、缓存音频等静态资源

## 启动步骤

建议按下面顺序启动。

### 1. 启动 AstrBot

确保 AstrBot 正常启动，并且该插件已经被加载。

如果插件加载成功，日志中通常会看到类似信息：

- `OLV Pet Adapter websocket listening on ws://127.0.0.1:12396`
- `OLV static resources listening on http://127.0.0.1:12397`

### 2. 启动前端

进入前端目录：

`C:\Users\Administrator\Downloads\weather-query\astrbot_plugin_self_open_llm_vtuber_web`

执行：

```powershell
npm run dev
```

或根据你的打包方式直接启动 Electron 产物。

### 3. 配置前端连接地址

前端需要连接到插件提供的地址：

- WebSocket URL：`ws://127.0.0.1:12396`
- Base URL：`http://127.0.0.1:12397`

如果前端和 AstrBot 不在同一台机器，请把地址改成实际可访问 IP。

### 4. 连接成功后测试

连接成功后，可以进行以下测试：

- 发送一条文本消息，确认 AstrBot 能回复
- 播放一条带 TTS 的消息，确认前端能拉到 `audio_url`
- 切换 `live2d_model_name`，确认模型能刷新
- 设置 `expression_provider_id`，确认回复时能带出表情动作

## 使用说明

### 文本对话

前端发送文本后，插件会：

1. 收到前端消息
2. 转成 AstrBot 事件
3. 走 AstrBot 常规对话流程
4. 将回复文本、音频、表情动作回传给前端

### 语音输入

当前支持两种音频输入相关链路：

- `mic-audio-data` / `mic-audio-end`
- `raw-audio-data`

插件会将语音内容送入 `stt_provider_id` 对应的 STT Provider 做识别。

### 表情播放

当启用 `expression_provider_id` 时，插件会根据：

- 人格设定
- 最近上下文
- 当前用户输入
- 当前回复文本

规划一个基础表情，并通过 `actions.expressions` 下发给前端。

如果回复没有音频，插件也会发送仅带动作的 `audio` 事件，让前端仍然可以应用表情。

### 模型切换

修改 `live2d_model_name` 后，插件会在运行时刷新配置，并重新向前端发送 `set-model-and-conf`。

如果切换后没有生效，优先检查：

- AstrBot 是否已经重载插件
- 前端是否仍连接旧会话
- 日志中是否出现新的 `set-model-and-conf`

## 常见问题

### 1. 前端连不上

优先检查：

- AstrBot 是否正常启动
- `12396` 和 `12397` 端口是否被占用
- 前端配置的 `wsUrl` / `baseUrl` 是否正确
- 防火墙是否拦截

### 2. 模型切换后没有生效

检查：

- `live2d_model_name` 是否是 [live2ds/model_dict.json](/c:/Users/Administrator/Downloads/AstrBot/data/plugins/astrbot_plugin_self_open_llm_vtuber/live2ds/model_dict.json) 中存在的名称
- AstrBot 日志里是否打印了新的模型配置
- 前端是否收到 `set-model-and-conf`

### 3. 表情规划模型没有生效

检查：

- `expression_provider_id` 是否填写正确
- 对应 Provider 是否在 AstrBot 中真实存在
- 日志里是否出现：
  - `Loaded expression planner provider from plugin config: ...`
  - `Planning base expression with provider: ...`

如果日志里出现的是别的模型，通常说明：

- 运行中的旧进程没有刷新 provider 绑定
- 或者你看的日志不是当前重启后的进程

### 4. 没有音频

检查：

- AstrBot 当前会话链路是否启用了 TTS
- TTS Provider 是否可用
- `ffmpeg` 是否安装正常
- 音频缓存目录 `olv/cache/audio` 是否有生成 wav 文件

### 5. 麦克风说话没反应

检查：

- `stt_provider_id` 是否配置
- STT Provider 是否可用
- `vad_model` 是否正常
- 前端是否成功发送 `mic-audio-data` 或 `raw-audio-data`

## 日志定位建议

建议重点关注这些日志来源：

- `astrbot_plugin_self_open_llm_vtuber.platform_adapter`
- `astrbot_plugin_self_open_llm_vtuber.static_resources`
- `sources.openai_source`
- `sources.volcengine_ark_source`

常见判断信号：

- WebSocket 是否启动成功
- 静态资源是否能返回 200
- 当前基础表情规划实际使用了哪个模型
- 表情动作是否已经写入 `actions`

## 当前已知说明

- 当前基础表情已经支持按回复内容自动播放
- 无音频回复时也可以播放表情
- `Mk6_1.0` 已支持自定义 Idle 动作
- 后续可以继续扩展到“基础表情 + 参数微调”的第二阶段

## 相关路径

- 插件目录：
  `C:\Users\Administrator\Downloads\AstrBot\data\plugins\astrbot_plugin_self_open_llm_vtuber`
- 插件配置：
  `C:\Users\Administrator\Downloads\AstrBot\data\config\astrbot_plugin_self_open_llm_vtuber_config.json`
- 前端目录：
  `C:\Users\Administrator\Downloads\weather-query\astrbot_plugin_self_open_llm_vtuber_web`

## 许可证与来源

本插件当前以 AstrBot 插件形式维护，前端桌宠工程参考 Open-LLM-VTuber 项目结构进行适配。
