# astrbot_plugin_self_open_llm_vtuber

这是一个运行在 AstrBot 内部的桌宠后端插件，用来把 AstrBot 的文本、语音、表情和动作结果桥接到定制版 `Open LLM Vtuber Web / Electron` 前端。

当前项目已经不是“原始 OLV 后端”的简单移植，而是一层围绕 AstrBot 场景定制的协议桥接层：

- 前端仓库：[murphys7017/astrbot_plugin_self_open_llm_vtuber_web](https://github.com/murphys7017/astrbot_plugin_self_open_llm_vtuber_web)
- 后端插件仓库：[murphys7017/astrbot_plugin_self_open_llm_vtuber](https://github.com/murphys7017/astrbot_plugin_self_open_llm_vtuber)
- 推荐运行方式：前端使用 `npm run dev`，后端由 AstrBot 插件提供 WebSocket 和静态资源服务

它的职责主要是：

- 接收前端文本、图片、语音输入，并转成 AstrBot 消息事件
- 提供前端所需的 WebSocket 服务
- 提供 `live2ds`、背景、头像、缓存音频等静态资源访问
- 把 AstrBot 回复转换成前端可消费的 `audio` / `control` / `set-model-and-conf` 等消息
- 基于模型配置和回复内容生成表情、动作与口型辅助数据

它不是独立后端服务，正确使用方式仍然是放进 AstrBot 插件目录运行。

![5](docs/img/5.png)

![4](docs/img/4.png)

![3](docs/img/3.png)

![2](docs/img/2.png)

## 当前项目定位

和前端仓库当前 README 对齐后，可以把这个后端理解为：

- AstrBot 负责对话、人格、Provider 调用、TTS/STT
- 本插件负责协议桥接、模型配置解析、音频缓存、表情动作打包
- 前端负责 Live2D 渲染、音频播放、字幕显示、口型同步、动作和表情应用

如果只更新前端而没有同步这个插件，很多能力不会正常工作，尤其是：

- `audio_url` 播放链路
- 动态 `model_info`
- `actions.expressions` / `actions.motions`
- `frontend-playback-complete` 驱动的 turn 收尾

## 相比原始方案的当前后端改动

### 1. 音频发送改成 `audio_url`

当前后端不再向前端发送整段 base64 音频，而是：

- 先把生成的音频转换成 wav
- 缓存到 AstrBot 插件数据目录下的 `cache/audio/`
- 再通过 `http://<host>:<http_port>/cache/audio/<uuid>.wav` 提供访问
- WebSocket 中只发送 `audio_url + volumes + display_text + actions`

这样可以减少消息体积，也更贴近浏览器和 Electron 的真实播放方式。

### 2. `model_info` 改为运行时动态解析

当前模型信息不再假设由前端写死，而是由后端在运行时解析并下发：

- 优先根据插件配置中的 `live2d_model_name`
- 从 `live2ds/model_dict.json` 中匹配对应模型
- 若模型不存在，再回退到平台适配器配置中的 `model_info_json`
- 最终在 `set-model-and-conf` 中下发给前端

如果 `model_info.url` 是相对路径，后端会自动补成 `http://<host>:<http_port>` 开头的完整 URL。

### 3. 表情和动作按模型配置驱动

当前后端会结合 `emotionMap`、`motionMap` 和可选的 `motion_catalog.json` 为前端构造动作数据：

- 根据 `base_expression` 生成 `actions.expressions`
- 根据 `motion_id`、`motionMap` 或 `motion_catalog` 生成 `actions.motions`
- 在没有音频时也会发送带动作的 `audio` 消息，让前端仍可显示字幕、表情和动作
- 优先支持主模型输出：

```text
<@anim {"motion_id":"thinking","base_expression":"confused"}>
```

同时仍兼容旧格式 `<~base_expression~>`。

### 4. 运行时按 turn 管理播放状态

当前后端已经和前端的新播放状态机对齐：

- 收到前端输入后先发送 `control: conversation-chain-start`
- 语音准备完成后发送 `audio`
- 再发送 `backend-synth-complete`
- 如果这轮有真实音频，等待前端回发 `frontend-playback-complete`
- 播放完成后发送 `force-new-message` 和 `control: conversation-chain-end`

无音频回复也会走相同的收尾语义，只是不会等待真实音频播放。

## 主要功能

- AstrBot 平台适配器，平台 ID 为 `olv_pet_adapter`
- WebSocket 服务，默认地址 `ws://127.0.0.1:12396`
- 静态资源服务，默认地址 `http://127.0.0.1:12397`
- 动态下发当前 Live2D 模型配置
- 支持文本、图片、麦克风音频输入
- 支持 STT 语音识别
- 支持基础表情规划与动作映射
- 支持无音频回复时仅下发表情 / 动作
- 支持本地缓存 TTS 音频并通过 HTTP 提供给前端播放
- 支持 `raw-audio-data` 的后端 VAD 断句

## 阶段文档

- 协议基线：
  [docs/protocol_baseline.md](docs/protocol_baseline.md)
- 当前一次联调审阅记录：
  [docs/审阅结果.md](docs/审阅结果.md)

## 安装方式

### 1. 放入 AstrBot 插件目录

将本插件目录放到 AstrBot 的插件目录中：

```text
AstrBot/data/plugins/astrbot_plugin_self_open_llm_vtuber
```

### 2. 安装 Python 依赖

当前依赖见 [requirements.txt](requirements.txt)：

- `websockets`
- `pydub`
- `numpy`
- `silero-vad`

可在 AstrBot 使用的 Python 环境中执行：

```powershell
pip install -r requirements.txt
```

如果你完全不用 `raw-audio-data`，理论上可以不安装 `silero-vad`，但当前默认依赖文件里已经包含它。

### 3. 安装 ffmpeg

插件会用 `pydub` 处理音频缓存，通常要求系统可用 `ffmpeg`。

如果出现音频转换失败、缓存 wav 生成失败等问题，请优先确认：

- `ffmpeg` 已安装
- `ffmpeg` 已加入系统 `PATH`

## 前端准备

本插件需要配合定制版桌宠前端一起使用，推荐仓库：

- [murphys7017/astrbot_plugin_self_open_llm_vtuber_web](https://github.com/murphys7017/astrbot_plugin_self_open_llm_vtuber_web)

前端安装依赖：

```powershell
npm install
```

开发模式启动：

```powershell
npm run dev
```

如果只需要 Web 调试页面：

```powershell
npm run dev:web
```

## 配置说明

当前项目有两层配置：

- AstrBot 插件配置：定义在 [_conf_schema.json](_conf_schema.json)
- 平台适配器配置：定义在 [platform_adapter.py](platform_adapter.py) 的 `default_config_tmpl`

### 插件配置项

#### `persona_id`

- 启动时使用的人格名称
- 留空时使用 AstrBot 当前默认人格

#### `chat_buffer_size`

- 表情规划时保留的最近对话条数
- 默认值：`10`

#### `image_cooldown_seconds`

- 图片输入冷却时间
- 默认值：`60`
- 在冷却时间内再次收到图片时，会丢弃新图片，仅保留文本

#### `live2d_model_name`

- 启动时加载的 Live2D 模型名称
- 默认值：`Mk6_1.0`
- 当前会优先从 `live2ds/model_dict.json` 中匹配该模型

#### `stt_provider_id`

- 指定优先使用的 STT Provider
- 留空时尝试使用 AstrBot 当前正在使用的 STT Provider

#### `expression_provider_id`

- 指定用于基础表情规划的聊天模型 Provider
- 只接收文本上下文，不处理音频输入
- 建议使用指令跟随较稳定的模型

#### `motion_candidate_limit`

- 注入给主模型的 `motion_id` 候选上限
- 默认值：`8`
- 设为 `0` 表示不限制
- 如果当前模型存在 `motion_catalog.json`，会优先把带语义描述的 catalog 候选注入提示词

#### `vad_model` 及相关参数

- 用于前端发送 `raw-audio-data` 时的后端断句
- 默认模型：`silero_vad`
- 当前实现使用独立的 `silero-vad` Python 包，不依赖上游 OLV 源码

相关参数包括：

- `vad_prob_threshold`
- `vad_db_threshold`
- `vad_required_hits`
- `vad_required_misses`
- `vad_smoothing_window`

### 平台适配器默认参数

平台适配器定义在 [platform_adapter.py](platform_adapter.py) 中，默认参数如下：

- `host`: `127.0.0.1`
- `port`: `12396`
- `http_port`: `12397`
- `conf_name`: `AstrBot Desktop`
- `conf_uid`: `astrbot-desktop`
- `speaker_name`: `AstrBot`
- `model_info_json`: `{}`
- `auto_start_mic`: `true`

说明：

- `port` 供前端 WebSocket 连接使用
- `http_port` 供前端加载模型、背景、头像和缓存音频等静态资源使用
- 建立连接后，如果 `auto_start_mic = true`，后端会向前端发送 `control: start-mic`

### `model_info` 的实际解析顺序

当前后端的模型配置解析顺序如下：

1. 先看插件配置里的 `live2d_model_name`
2. 到 `live2ds/model_dict.json` 中查找同名模型
3. 找不到时再回退到平台配置 `model_info_json`
4. 如果两者都不可用，则回退到 `model_dict.json` 第一项

因此通常推荐：

- 日常切换模型时，优先改 `live2d_model_name`
- 仅在临时调试特殊模型时，再考虑直接改 `model_info_json`

## 使用步骤

### 1. 启动 AstrBot

先正常启动 AstrBot，并确认插件已被加载。

正常情况下，日志里会看到类似内容：

- `OLV Pet Adapter websocket listening on ws://127.0.0.1:12396`
- `Desktop VTuber static resources listening on http://127.0.0.1:12397`

### 2. 启动前端

进入前端目录并启动：

```powershell
npm run dev
```

或者直接运行已经构建好的 Electron 客户端。

### 3. 配置前端连接地址

前端需要连接到插件提供的两个地址：

- WebSocket URL：`ws://127.0.0.1:12396`
- Base URL：`http://127.0.0.1:12397`

如果前端和 AstrBot 不在同一台机器，请改成实际 IP。

### 4. 开始对话

连接成功后，前端输入会进入 AstrBot 正常消息流程；AstrBot 返回的文本、音频、表情和动作会再由插件转回前端。

## 当前最关键的协议和运行链路

### 前端 -> 后端

当前主链路常用消息包括：

- `text-input`
- `mic-audio-data`
- `mic-audio-end`
- `frontend-playback-complete`

可选 / 兼容消息包括：

- `raw-audio-data`
- `interrupt-signal`
- 一组旧前端兼容消息，如 `fetch-backgrounds`、`heartbeat`、`switch-config`

### 后端 -> 前端

当前主链路常用消息包括：

- `set-model-and-conf`
- `control`
- `audio`
- `backend-synth-complete`
- `force-new-message`
- `full-text`
- `error`
- `user-input-transcription`

其中 `audio` 负载的关键字段包括：

- `audio_url`
- `volumes`
- `slice_length`
- `display_text`
- `actions.expressions`
- `actions.motions`
- `actions.expression_decision`
- `actions.pictures`

协议基线请以 [docs/protocol_baseline.md](docs/protocol_baseline.md) 为准。

## 当前桌宠主流程

可以把现在的后端主流程理解为：

1. 前端建立连接
2. 后端发送 `Connection established`
3. 后端发送 `set-model-and-conf`
4. 用户发送文本、图片或麦克风音频
5. 插件把输入转成 AstrBot 消息事件
6. AstrBot 返回文本、语音和动作规划结果
7. 如输入来自语音，后端可先回发 `user-input-transcription`
8. 后端把语音缓存成可访问的 `audio_url`
9. 后端发送 `audio + display_text + actions`
10. 后端发送 `backend-synth-complete`
11. 前端真实播放完成后回发 `frontend-playback-complete`
12. 后端发送 `force-new-message` 与 `conversation-chain-end`

如果这轮没有音频，后端仍会发送带 `actions` 的 `audio` 负载，让前端保持统一消费方式。

## 目录说明

- [main.py](main.py)
  插件入口，同时在 LLM 请求/响应阶段注入和提取动作标签
- [platform_adapter.py](platform_adapter.py)
  平台适配器入口，负责初始化运行时状态、WebSocket、静态资源服务
- [platform_event.py](platform_event.py)
  AstrBot 事件包装
- [static_resources.py](static_resources.py)
  静态资源 HTTP 服务
- [adapter](adapter)
  协议、运行时、表情规划、消息构造、音频缓存等辅助模块
- [live2ds](live2ds)
  插件内置 Live2D 模型资源和模型配置
- [docs/protocol_baseline.md](docs/protocol_baseline.md)
  当前前后端协议基线

## 常见问题

### 前端连接不上

优先检查：

- AstrBot 是否已经启动
- 插件是否加载成功
- `12396` / `12397` 端口是否被占用
- 前端 `wsUrl` / `baseUrl` 是否填写正确
- 本机防火墙是否拦截
- 是否已经有另一个前端客户端连接中

说明：当前后端只支持单客户端连接，同时连接第二个前端时会被拒绝。

### 模型切换不生效

检查：

- `live2d_model_name` 是否存在于 `live2ds/model_dict.json`
- AstrBot 日志里是否出现新的 `set-model-and-conf`
- 前端是否仍停留在旧会话

### 表情规划或动作不生效

检查：

- `expression_provider_id` 是否填写正确
- Provider 是否真实存在于 AstrBot 中
- 当前模型是否配置了 `emotionMap` / `motionMap`
- 若使用 `motion_id`，对应模型是否存在 `motion_catalog.json` 或可匹配的 `motionMap`

日志里可重点关注：

- `Loaded expression planner provider from plugin config: ...`
- `Planning base expression with provider: ...`
- `[Live2DExpr] hook response extracted ...`

### 没有音频

检查：

- AstrBot 当前对话链路是否启用了 TTS
- TTS Provider 是否可用
- `ffmpeg` 是否正常
- AstrBot 插件数据目录下的 `cache/audio/` 是否成功生成 wav 缓存

### 麦克风输入无反应

检查：

- `stt_provider_id` 是否配置
- STT Provider 是否可用
- 前端是否成功发送 `mic-audio-data` / `mic-audio-end`
- 如果走 `raw-audio-data`，`silero-vad` 是否可用

## 日志排查建议

建议重点关注以下日志来源：

- `astrbot_plugin_self_open_llm_vtuber.platform_adapter`
- `astrbot_plugin_self_open_llm_vtuber.static_resources`
- `astrbot_plugin_self_open_llm_vtuber.adapter`
- 你当前实际使用的 STT / TTS / 聊天模型 Provider 日志

这些日志通常能帮助确认：

- WebSocket 是否正常监听
- 静态资源是否正常返回
- 当前模型配置是否正确解析
- 当前表情规划实际用了哪个 Provider
- 返回消息里是否成功写入动作与音频 URL

## 说明

当前插件定位仍然是 AstrBot 的桌宠桥接层，不替代 AstrBot 主对话系统，也不替代前端渲染器本身。

更准确地说：

- AstrBot 负责消息处理、人格、Provider 调用
- 本插件负责协议桥接、音频缓存、模型配置解析、动作表情打包
- 前端负责 Live2D 渲染、口型同步、字幕显示、动作播放和界面交互
