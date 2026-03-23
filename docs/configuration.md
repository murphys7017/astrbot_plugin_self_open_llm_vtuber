# 配置参考

本文档汇总本插件的可配置项。`README.md` 保留快速使用说明，详细字段含义统一放在这里。

## 配置分层

- 插件配置：`_conf_schema.json`
- 平台适配器配置：`platform_adapter.py` 中 `default_config_tmpl`

## 插件配置（_conf_schema.json）

### `persona_id`

- 类型：`string`
- 默认值：`""`
- 说明：启动时使用的人格名称；留空时使用 AstrBot 当前默认人格。

### `chat_buffer_size`

- 类型：`int`
- 默认值：`10`
- 说明：表情规划阶段缓存最近对话条数。

### `image_cooldown_seconds`

- 类型：`int`
- 默认值：`60`
- 说明：图片输入冷却时间（秒）；冷却窗口内再次收到图片时会丢弃新图片，仅保留文本。

### `live2d_model_name`

- 类型：`string`
- 默认值：`Mk6_1.0`
- 说明：启动时加载的 Live2D 模型名，需存在于 `live2ds/model_dict.json`。

### `stt_provider_id`

- 类型：`string`
- 默认值：`""`
- 说明：优先使用的 STT Provider；留空时尝试使用 AstrBot 当前 STT Provider。

### `expression_provider_id`

- 类型：`string`
- 默认值：`""`
- 说明：用于基础情绪/基础表情判断的聊天模型 Provider（仅文本上下文）。

### `motion_candidate_limit`

- 类型：`int`
- 默认值：`8`
- 说明：注入主模型提示词的 `motion_id` 候选上限；`0` 表示不限制。

### `vad_model`

- 类型：`string`
- 默认值：`silero_vad`
- 说明：前端发送 `raw-audio-data` 时使用的后端断句模型。

### `vad_prob_threshold`

- 类型：`float`
- 默认值：`0.4`
- 说明：VAD 语音概率阈值。

### `vad_db_threshold`

- 类型：`int`
- 默认值：`60`
- 说明：VAD 分贝阈值。

### `vad_required_hits`

- 类型：`int`
- 默认值：`3`
- 说明：VAD 连续命中次数阈值。

### `vad_required_misses`

- 类型：`int`
- 默认值：`24`
- 说明：VAD 连续静音次数阈值。

### `vad_smoothing_window`

- 类型：`int`
- 默认值：`5`
- 说明：VAD 平滑窗口大小。

## 平台适配器配置（default_config_tmpl）

- `host`: `127.0.0.1`
- `port`: `12396`（WebSocket）
- `http_port`: `12397`（静态资源/缓存音频）
- `conf_name`: `AstrBot Desktop`
- `conf_uid`: `astrbot-desktop`
- `speaker_name`: `AstrBot`
- `model_info_json`: `{}`
- `auto_start_mic`: `true`

## `model_info` 解析顺序

1. 优先读取插件配置 `live2d_model_name`
2. 在 `live2ds/model_dict.json` 查找同名模型
3. 未命中时回退到平台配置 `model_info_json`
4. 两者不可用时回退到 `model_dict.json` 第一项

建议：

- 日常切模型优先改 `live2d_model_name`
- 仅调试特殊模型时再使用 `model_info_json`
