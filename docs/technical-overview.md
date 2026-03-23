# Alice 的桌面分身 技术说明

本文档面向需要了解实现机制、协议与运行链路的开发者。

## 项目定位

- AstrBot：对话、人格、Provider 调用、TTS/STT
- 本插件：协议桥接、模型配置解析、音频缓存、表情动作打包
- 前端：Live2D 渲染、音频播放、字幕显示、动作和表情应用

## 关键能力设计

### 音频以 `audio_url` 方式下发

- 音频转换为 wav 后缓存到插件数据目录 `cache/audio/`
- 前端通过 `http://<host>:<http_port>/cache/audio/<uuid>.wav` 拉取
- WebSocket 主要下发 `audio_url + volumes + display_text + actions`

### `model_info` 运行时动态解析

- 优先读取 `live2d_model_name`
- 优先匹配 `live2ds/model_dict.json`
- 未命中时回退 `model_info_json`
- 相对路径会补全为 `http://<host>:<http_port>` 绝对地址

### 表情与动作按模型配置驱动

- 表情来源：`base_expression` -> `actions.expressions`
- 动作来源：`motion_id`/`motionMap`/`motion_catalog.json` -> `actions.motions`
- 无音频回复仍会发送带 `actions` 的 `audio` 消息，保证前端消费路径统一
- 兼容主格式与旧格式：

```text
<@anim {"motion_id":"thinking","base_expression":"confused"}>
<~base_expression~>
```

### 按 turn 协调播放状态

- 输入后先发 `control: conversation-chain-start`
- 合成阶段发 `audio`，随后发 `backend-synth-complete`
- 有真实音频时等待前端 `frontend-playback-complete`
- 收尾发 `force-new-message` 与 `control: conversation-chain-end`

## 协议主链路（摘要）

### 前端 -> 后端

- `text-input`
- `mic-audio-data`
- `mic-audio-end`
- `frontend-playback-complete`
- 可选：`raw-audio-data`、`interrupt-signal` 及兼容消息

### 后端 -> 前端

- `set-model-and-conf`
- `control`
- `audio`
- `backend-synth-complete`
- `force-new-message`
- `full-text`
- `error`
- `user-input-transcription`

字段级协议请以 [protocol_baseline.md](protocol_baseline.md) 为准。

## 运行流程（摘要）

1. 前端建立连接
2. 后端发送 `Connection established` 与 `set-model-and-conf`
3. 用户输入进入 AstrBot 消息链路
4. AstrBot 返回文本/语音/动作规划结果
5. 后端缓存音频并下发 `audio + actions`
6. 后端下发 `backend-synth-complete`
7. 前端回发 `frontend-playback-complete` 后收尾

## 代码结构

- `main.py`：插件入口，处理动作标签注入与提取
- `platform_adapter.py`：平台适配器入口，初始化运行时与服务
- `static_resources.py`：静态资源 HTTP 服务
- `adapter/`：协议、运行时、表情规划、消息构建、音频缓存
- `live2ds/`：模型资源与模型配置

## 限制与注意

- 当前后端仅支持单客户端连接
- 前后端版本需要同步升级，否则可能出现协议能力不匹配
