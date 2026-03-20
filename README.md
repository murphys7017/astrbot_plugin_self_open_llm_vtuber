# astrbot_plugin_self_open_llm_vtuber

这是一个 **AstrBot 插件**，用于把 AstrBot 的对话、语音和表情结果对接到 open llm vtuber 前端。

插件本身运行在 AstrBot 内部，主要负责：

- 提供桌宠前端所需的 WebSocket 服务
- 提供模型、缓存音频等静态资源访问
- 将前端输入转成 AstrBot 消息事件
- 将 AstrBot 回复转成前端可播放的文本、音频、表情动作
- 根据回复内容规划基础表情

它不是一个独立的后端项目，正确的使用方式是：**把它安装到 AstrBot 的插件目录中运行**。

![5](docs/img/5.png)

![4](docs/img/4.png)

![3](docs/img/3.png)

![2](docs/img/2.png)

## 主要功能

- AstrBot 平台适配器，平台 ID 为 `olv_pet_adapter`
- WebSocket 服务，默认地址 `ws://127.0.0.1:12396`
- 静态资源服务，默认地址 `http://127.0.0.1:12397`
- 支持 Live2D 模型切换
- 支持 STT 语音识别
- 支持基础表情规划
- 支持无音频回复时仅播放表情
- 支持本地缓存 TTS 音频并通过 HTTP 提供给前端播放

## 安装方式

### 1. 放入 AstrBot 插件目录

将本插件目录放到 AstrBot 的插件目录中：

```text
AstrBot/data/plugins/astrbot_plugin_self_open_llm_vtuber
```

如果你已经是在这个目录下开发，保持当前位置即可。

### 2. 安装 Python 依赖

插件依赖以下常见包：

- `websockets`
- `pydub`
- `numpy`
- `silero-vad`（仅在启用 `raw-audio-data` 后端 VAD 时需要）

如主环境未安装，可在 AstrBot 所用 Python 环境中执行：

```powershell
pip install websockets pydub numpy silero-vad
```

如果你完全不使用 `raw-audio-data`，也可以不安装 `silero-vad`。

### 3. 安装 ffmpeg

插件会用 `pydub` 处理音频缓存，通常需要系统中可用的 `ffmpeg`。

如果出现音频转换失败、缓存 wav 生成失败等问题，请先确认：

- `ffmpeg` 已安装
- `ffmpeg` 已加入系统 PATH

## 前端准备

本插件需要配合open llm vtuber web前端项目一起使用。推荐使用我修改过的[murphys7017/astrbot_plugin_self_open_llm_vtuber_web: The Web/Electron frontend for Open-LLM-VTuber Project](https://github.com/murphys7017/astrbot_plugin_self_open_llm_vtuber_web)

然后：

```powershell
npm install
```

开发模式启动：

```powershell
npm run dev
```

仅启动 Web 调试页面：

```powershell
npm run dev:web
```

## AstrBot 插件配置

配置项定义位于：

[_conf_schema.json](/_conf_schema.json)

常用配置如下。

### `persona_id`

- 启动时使用的人格名称
- 留空时使用 AstrBot 当前默认人格

### `chat_buffer_size`

- 用于表情规划时保留最近多少条用户 / 助手文本
- 默认值：`10`

### `live2d_model_name`

- 指定启动时加载的 Live2D 模型名称
- 当前常用值：
  - `mao_pro`
  - `Mk6_1.0`

### `stt_provider_id`

- 指定优先使用的 STT Provider
- 例如：`whisper`

### `expression_provider_id`

- 指定用于基础表情规划的聊天模型 Provider
- 这一部分只接收文本上下文，不处理音频输入
- 建议使用指令跟随较稳定的模型
- 例如：`volcengine_ark/GLM-4.7`

### `vad_model` 及相关参数

- 用于前端发送 `raw-audio-data` 时的后端断句
- 默认模型：`silero_vad`
- 当前实现使用独立的 `silero-vad` Python 包
- 不再依赖 Open-LLM-VTuber 源码

相关参数：

- `vad_prob_threshold`
- `vad_db_threshold`
- `vad_required_hits`
- `vad_required_misses`
- `vad_smoothing_window`

## 平台适配器默认参数

平台适配器定义在 [platform_adapter.py](/platform_adapter.py) 中，默认参数如下：

- `host`: `127.0.0.1`
- `port`: `12396`
- `http_port`: `12397`
- `conf_name`: `AstrBot Desktop`
- `conf_uid`: `astrbot-desktop`
- `speaker_name`: `AstrBot`
- `auto_start_mic`: `true`

说明：

- `port` 供前端 WebSocket 连接使用
- `http_port` 供前端加载模型、背景、缓存音频等静态资源使用

## 使用步骤

### 1. 启动 AstrBot

先正常启动 AstrBot，并确认插件已经被加载。

正常情况下，日志里会看到类似内容：

- `Desktop VTuber Adapter websocket listening on ws://127.0.0.1:12396`
- `Desktop VTuber static resources listening on http://127.0.0.1:12397`

### 2. 启动前端

进入前端目录并启动：

```powershell
npm run dev
```

或直接运行你已经构建好的 Electron 客户端。

### 3. 配置前端连接地址

前端需要连接到插件提供的两个地址：

- WebSocket URL：`ws://127.0.0.1:12396`
- Base URL：`http://127.0.0.1:12397`

如果前端和 AstrBot 不在同一台机器，请改成实际 IP 地址。

### 4. 开始对话

连接成功后，前端发来的文本或音频会进入 AstrBot 的正常消息流程；AstrBot 返回的文本、音频和表情动作会再被插件转回前端。

## 工作流程

### 文本输入

前端发送文本后，插件会：

1. 接收 WebSocket 消息
2. 转换成 AstrBot 消息事件
3. 进入 AstrBot 正常对话链路
4. 将回复文本、音频和动作打包发回前端

### 语音输入

插件支持处理以下前端音频消息：

- `mic-audio-data`
- `mic-audio-end`
- `raw-audio-data`

收到音频后，会通过 `stt_provider_id` 对应的 STT Provider 转成文字，再交给 AstrBot。

说明：

- 当前推荐使用 `mic-audio-data` + `mic-audio-end`
- 如果启用 `raw-audio-data`，请确认运行环境已安装 `silero-vad`

### 表情规划

当配置了 `expression_provider_id` 后，插件会结合以下信息规划基础表情：

- 当前人格设定
- 最近对话上下文
- 当前用户输入
- 当前回复文本

规划结果会通过 `actions.expressions` 和 `actions.expression_decision` 发送给前端。

即使这次回复没有音频，插件也会发送带动作的消息，让前端依然可以播放表情。

### 模型切换

修改 `live2d_model_name` 后，插件会在运行时刷新配置，并重新向前端发送 `set-model-and-conf`。

## 目录说明

- [main.py](/c:/Users/Administrator/Downloads/AstrBot/data/plugins/astrbot_plugin_self_open_llm_vtuber/main.py)
  插件入口
- [platform_adapter.py](/c:/Users/Administrator/Downloads/AstrBot/data/plugins/astrbot_plugin_self_open_llm_vtuber/platform_adapter.py)
  核心平台适配器
- [platform_event.py](/c:/Users/Administrator/Downloads/AstrBot/data/plugins/astrbot_plugin_self_open_llm_vtuber/platform_event.py)
  AstrBot 事件包装
- [static_resources.py](/c:/Users/Administrator/Downloads/AstrBot/data/plugins/astrbot_plugin_self_open_llm_vtuber/static_resources.py)
  静态资源 HTTP 服务
- [docs/protocol_baseline.md](/c:/Users/Administrator/Downloads/AstrBot/data/plugins/astrbot_plugin_self_open_llm_vtuber/docs/protocol_baseline.md)
  当前前后端 WebSocket 协议基线
- [adapter](/c:/Users/Administrator/Downloads/AstrBot/data/plugins/astrbot_plugin_self_open_llm_vtuber/adapter)
  表情规划、协议处理、运行时配置等辅助模块
- [live2ds](/c:/Users/Administrator/Downloads/AstrBot/data/plugins/astrbot_plugin_self_open_llm_vtuber/live2ds)
  插件内置 Live2D 模型资源

## 常见问题

### 前端连接不上

优先检查：

- AstrBot 是否已经启动
- 插件是否加载成功
- `12396` / `12397` 端口是否被占用
- 前端的 `wsUrl` / `baseUrl` 是否填写正确
- 本机防火墙是否拦截

### 模型切换不生效

检查：

- `live2d_model_name` 是否存在于模型配置中
- AstrBot 日志是否出现新的 `set-model-and-conf`
- 前端是否仍连接旧会话

### 表情规划模型不生效

检查：

- `expression_provider_id` 是否填写正确
- Provider 是否真实存在于 AstrBot 中
- 日志是否出现：
  - `Loaded expression planner provider from plugin config: ...`
  - `Planning base expression with provider: ...`

### 没有音频

检查：

- AstrBot 当前对话链路是否启用了 TTS
- TTS Provider 是否可用
- `ffmpeg` 是否正常
- `olv/cache/audio` 是否成功生成 wav 缓存

### 麦克风输入无反应

检查：

- `stt_provider_id` 是否配置
- STT Provider 是否可用
- `vad_model` 是否正常
- 前端是否成功发送音频消息

## 日志排查建议

建议重点关注以下日志来源：

- `astrbot_plugin_self_open_llm_vtuber.platform_adapter`
- `astrbot_plugin_self_open_llm_vtuber.static_resources`
- `sources.openai_source`
- `sources.volcengine_ark_source`

这些日志通常能帮助确认：

- WebSocket 是否正常监听
- 静态资源是否返回成功
- 当前表情规划实际用了哪个模型
- 表情动作是否成功写入返回消息

## 说明

当前插件定位是 AstrBot 插件桥接层，不负责替代 AstrBot 主对话系统，也不负责替代前端渲染器本身。

更准确地说：

- AstrBot 负责消息处理、人格、Provider 调用
- 本插件负责协议桥接、音频缓存、表情动作打包
- 前端负责 Live2D 渲染、口型播放、表情应用和界面交互
