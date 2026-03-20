# Desktop VTuber Protocol Baseline

本文件是 `astrbot_plugin_self_open_llm_vtuber` 与
`astrbot_plugin_self_open_llm_vtuber_web` 当前协作协议的单一基线说明。

目标：

- 明确当前真实在跑的 WebSocket 消息类型
- 标注发送方 / 接收方
- 标注消息字段
- 标注哪些属于兼容消息、哪些存在漂移

当前基线版本：`2026-03`

## 1. 当前推荐主链路

### 前端 -> 后端

#### `text-input`

- 发送方：前端
- 接收方：后端
- 作用：发送文本输入，可附带图片
- 字段：
  - `type: "text-input"`
  - `text: string`
  - `images?: list`

#### `mic-audio-data`

- 发送方：前端
- 接收方：后端
- 作用：发送麦克风分片音频
- 字段：
  - `type: "mic-audio-data"`
  - `audio: number[]`

#### `mic-audio-end`

- 发送方：前端
- 接收方：后端
- 作用：标记一次音频输入结束，可附带图片
- 字段：
  - `type: "mic-audio-end"`
  - `images?: list`

#### `frontend-playback-complete`

- 发送方：前端
- 接收方：后端
- 作用：告知前端播放完成，用于结束 turn
- 字段：
  - `type: "frontend-playback-complete"`

### 后端 -> 前端

#### `set-model-and-conf`

- 发送方：后端
- 接收方：前端
- 作用：下发当前 Live2D 模型与前端配置
- 字段：
  - `type: "set-model-and-conf"`
  - `model_info: object`
  - `conf_name: string`
  - `conf_uid: string`
  - `client_uid: string`

#### `control`

- 发送方：后端
- 接收方：前端
- 作用：控制前端状态机
- 字段：
  - `type: "control"`
  - `text: string`

当前已知控制值：

- `start-mic`
- `stop-mic`
- `conversation-chain-start`
- `conversation-chain-end`
- `interrupt`
- `mic-audio-end`

#### `audio`

- 发送方：后端
- 接收方：前端
- 作用：发送音频播放任务
- 字段：
  - `type: "audio"`
  - `audio_url?: string | null`
  - `volumes?: number[]`
  - `slice_length?: number`
  - `display_text?: { text, name, avatar }`
  - `actions?: { expressions?, motions?, expression_decision?, pictures?, sounds? }`
  - `forwarded?: boolean`

#### `backend-synth-complete`

- 发送方：后端
- 接收方：前端
- 作用：通知后端音频已准备完成
- 字段：
  - `type: "backend-synth-complete"`

#### `force-new-message`

- 发送方：后端
- 接收方：前端
- 作用：强制下一条消息开新气泡
- 字段：
  - `type: "force-new-message"`

#### `full-text`

- 发送方：后端
- 接收方：前端
- 作用：纯文本输出或连接提示
- 字段：
  - `type: "full-text"`
  - `text: string`

#### `error`

- 发送方：后端
- 接收方：前端
- 作用：错误提示
- 字段：
  - `type: "error"`
  - `message: string`

#### `user-input-transcription`

- 发送方：后端
- 接收方：前端
- 作用：显示 STT 转写结果
- 字段：
  - `type: "user-input-transcription"`
  - `text: string`

## 2. 当前兼容消息

这些消息当前主要用于兼容旧前端工作流，属于“存在但不一定完整实现”的协议面。

### 前端 -> 后端

- `fetch-backgrounds`
- `fetch-configs`
- `fetch-history-list`
- `create-new-history`
- `fetch-and-set-history`
- `delete-history`
- `switch-config`
- `request-init-config`
- `heartbeat`
- `audio-play-start`
- `raw-audio-data`

### 后端 -> 前端

- `background-files`
- `config-files`
- `history-list`
- `history-data`
- `new-history-created`
- `history-deleted`
- `config-switched`
- `heartbeat-ack`
- `group-update`

## 3. 已知漂移 / 未完全收敛项

### 1. `heartbeat-ack`

- 后端会发
- 前端当前只需要忽略
- 不参与主链路状态机

### 2. `group-update`

- 后端初始化时会发
- 前端当前只需要忽略
- 不参与当前单前端桌宠主流程

### 3. `conversation-chain-end`

- 当前推荐走法：作为 `control.text = "conversation-chain-end"` 传递
- 前端仍保留了顶层 `message.type === "conversation-chain-end"` 的兼容分支
- 该顶层消息类型应视为旧兼容路径

### 4. `interrupt-signal`

- 前端会发送
- 前端也保留了接收分支
- 后端当前主协议未正式接入该消息
- 这属于待设计项，不应在没有明确语义前直接扩展

### 5. `ai-speak-signal`

- 前端会发送
- 后端当前未正式接入
- 属于未来能力，不在当前桌宠主链路基线内

### 6. `switch-config.file`

- 前端发送 `file`
- 后端当前只返回“未启用”
- 字段已存在，但功能未正式实现

## 4. 收敛原则

从现在开始，协议演进按以下原则处理：

1. 新消息类型必须先更新本文件
2. 新字段必须先更新本文件
3. 兼容消息必须明确标记为：
   - 主链路
   - 兼容
   - 未来计划
4. 如果后端发送了前端不消费的消息，或前端发送了后端不处理的消息，必须在本文件“已知漂移”中登记
