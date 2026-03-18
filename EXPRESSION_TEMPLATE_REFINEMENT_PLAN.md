# 表情模板微调改造计划书

## 一、目标

把当前“表情标签 -> 本地参数模板”的系统，进一步升级为：

1. 先确定基础情绪
2. 再选一个基础表情模板
3. 再输出少量微调参数
4. 本地把“基础模板 + 微调参数”合成为一个虚拟 expression
5. 前端执行这个虚拟 expression

本方案的核心目的：

- 不让 LLM 直接随意输出大量底层参数
- 不把系统绑定死在固定标签模板上
- 让多个 Live2D 模型都可以通过“模板 + 微调白名单”接入


## 二、设计原则

### 1. 两阶段保留

仍然保留两阶段：

- 第一阶段：大模型负责规划表情意图
- 第二阶段：小模型负责模板选择和微调参数

### 2. 小模型不直接生成整套 raw 参数

第二阶段只允许输出：

- `template_name`
- `refinements`
- `duration_ms`
- `transition_ms`

而不是直接输出全量 Live2D 参数。

### 3. 最终由本地合成虚拟 expression

系统最终执行的不是小模型原始输出，而是：

```text
基础模板参数 + 微调参数 = 最终虚拟 expression
```

### 4. 先做“虚拟 exp3”，不急着落盘成真实文件

第一阶段实现时，虚拟 expression 只存在于内存里，不真的写成磁盘文件。

后续如果有需要，再加“导出/缓存为 exp3.json”能力。


## 三、最终想要的数据流

```text
用户输入
-> 主模型生成回复文本
-> 按句子/语义分段
-> 第一阶段大模型：生成基础情绪和基础回复段表情规划
-> 第二阶段小模型：为每段选择基础模板 + 输出微调参数
-> 后端合成虚拟 expression
-> 前端执行 base_expression + 虚拟 expression
```


## 四、模型配置结构

不新增 `expression_profile.json` 概念，直接围绕“模型可用的模板与微调参数能力”设计。

建议每个模型有一份独立配置文件，例如：

- `live2ds/mao_pro/expression_templates.json`
- `live2ds/Mk6_1.0/expression_templates.json`

这个文件负责描述：

1. 基础表情映射
2. 基础模板定义
3. 微调参数白名单
4. 微调参数安全范围


## 五、建议的模型配置文件结构

建议结构如下：

```json
{
  "version": "1.0",
  "model_name": "Mk6_1.0",
  "default_expression": "neutral",
  "base_expression_map": {
    "neutral": 0,
    "happy": 1,
    "angry": 2,
    "surprised": 3,
    "confused": 5,
    "embarrassed": 6,
    "tired": 8,
    "thinking": 12
  },
  "expression_templates": {
    "neutral": {
      "base_expression": "neutral",
      "default_params": {}
    },
    "happy": {
      "base_expression": "happy",
      "default_params": {
        "ParamMouthForm": 0.22,
        "ParamMouthOpenY": 0.08
      }
    },
    "angry": {
      "base_expression": "angry",
      "default_params": {
        "ParamMouthForm": -0.2,
        "ParamBrowForm": 0.25,
        "ParamAngleY": -4,
        "ParamBodyAngleX": 2
      }
    }
  },
  "refinement_params": {
    "ParamAngleX": { "min": -12, "max": 12 },
    "ParamAngleY": { "min": -8, "max": 8 },
    "ParamAngleZ": { "min": -10, "max": 10 },
    "ParamBodyAngleX": { "min": -6, "max": 6 },
    "BodyAngleY": { "min": -4, "max": 4 },
    "ParamBodyAngleZ": { "min": -6, "max": 6 },
    "ParamMouthOpenY": { "min": -0.25, "max": 0.25 },
    "ParamMouthForm": { "min": -0.35, "max": 0.35 },
    "ParamMouthX": { "min": -0.2, "max": 0.2 },
    "ParamBrowForm": { "min": -0.3, "max": 0.3 },
    "ParamEyeLOpen": { "min": -0.2, "max": 0.2 },
    "ParamEyeROpen": { "min": -0.2, "max": 0.2 },
    "ParamEyeBallX": { "min": -0.25, "max": 0.25 },
    "ParamEyeBallY": { "min": -0.2, "max": 0.2 }
  }
}
```


## 六、阶段一输出协议

第一阶段大模型负责输出“基础情绪规划”。

建议协议：

```json
{
  "version": "1.0",
  "segments": [
    {
      "index": 0,
      "text": "谁、谁想骂你啊！",
      "semantic_expression": "angry",
      "duration_ms": 1200,
      "transition_ms": 180
    }
  ]
}
```

说明：

- `semantic_expression` 只表示语义层情绪
- 不包含模板名
- 不包含参数


## 七、阶段二输出协议

第二阶段小模型读取：

- persona
- chatbuffer
- 用户输入
- 分段回复文本
- 阶段一结果
- 当前模型可用模板名
- 当前模型允许微调的参数名

建议输出协议：

```json
{
  "version": "1.0",
  "segments": [
    {
      "index": 0,
      "text": "谁、谁想骂你啊！",
      "semantic_expression": "angry",
      "template_name": "angry",
      "refinements": {
        "ParamAngleX": -3,
        "ParamBodyAngleX": 1.2,
        "ParamMouthForm": -0.08
      },
      "duration_ms": 1200,
      "transition_ms": 180
    }
  ]
}
```

说明：

- `template_name` 必须从模型模板集合中选择
- `refinements` 只能使用白名单参数
- `refinements` 的值必须在安全范围内


## 八、虚拟 expression 合成规则

后端合成逻辑：

```text
虚拟 expression = expression_templates[template_name].default_params + refinements
```

也就是：

1. 找到模板对应的 `base_expression`
2. 取模板的 `default_params`
3. 对 `refinements` 做：
   - 参数白名单过滤
   - min/max clamp
4. 合并成一份最终参数字典

推荐合成结果结构：

```json
{
  "base_expression": 2,
  "semantic_expression": "angry",
  "template_name": "angry",
  "template_params": {
    "ParamMouthForm": -0.2,
    "ParamBrowForm": 0.25,
    "ParamAngleY": -4,
    "ParamBodyAngleX": 2
  },
  "refinement_params": {
    "ParamAngleX": -3,
    "ParamBodyAngleX": 1.2,
    "ParamMouthForm": -0.08
  },
  "merged_params": {
    "ParamMouthForm": -0.28,
    "ParamBrowForm": 0.25,
    "ParamAngleY": -4,
    "ParamBodyAngleX": 3.2,
    "ParamAngleX": -3
  },
  "duration_ms": 1200,
  "transition_ms": 180
}
```


## 九、前端执行逻辑

前端最终只需要执行：

1. 应用 `base_expression`
2. 再应用 `merged_params`

说明：

- `base_expression` 解决基础表情资源切换
- `merged_params` 解决当前语句的动态姿态/微表情差异

前端不需要知道：

- 模板是怎么来的
- 小模型是怎么推理的

前端只负责执行最终结果。


## 十、与当前系统的关系

当前系统的 `expression_plan` / `compiled_expression_plan` 之后要逐步迁移成：

### 当前

- `base_expression`
- `head_style`
- `body_style`
- `face_style`
- `amplitude_level`

### 未来

- `semantic_expression`
- `template_name`
- `refinements`
- `merged_params`

也就是说：

当前“标签模板系统”是第一阶段过渡方案；
未来“基础模板 + 微调参数 + 虚拟 expression”是目标方案。


## 十一、实施步骤

### 第一步：配置抽离

新增模型级配置文件：

- `expression_templates.json`

实现：

- 后端按当前模型读取对应配置
- 不再依赖代码里硬编码的模板常量

### 第二步：阶段一协议改造

把第一阶段输出从：

- 直接输出 `head_style/body_style/face_style`

改成：

- 输出 `semantic_expression`

### 第三步：阶段二协议改造

把第二阶段输出改成：

- `template_name`
- `refinements`

### 第四步：虚拟 expression 编译器

实现：

- `template_name -> base_expression + default_params`
- `refinements -> 过滤 + clamp`
- 合并生成 `merged_params`

### 第五步：前端执行器适配

前端执行结构改为：

- `base_expression`
- `merged_params`

无需关心模板细节。


## 十二、风险与约束

### 风险 1

模板配置不合理，会导致不同模型表现不一致。

解决：

- 每个模型独立配置

### 风险 2

微调参数过多，LLM 仍然可能不稳定。

解决：

- 只开放少量白名单参数

### 风险 3

真实写入临时 `exp3.json` 文件会引入额外文件生命周期管理问题。

解决：

- 第一阶段先只做“内存中的虚拟 expression”
- 后续需要缓存/导出时再落盘


## 十三、结论

最终方案建议如下：

- 不新增 `expression_profile.json` 概念
- 直接使用每个模型自己的 `expression_templates.json`
- 第一阶段决定基础情绪
- 第二阶段决定模板与微调参数
- 本地合成虚拟 expression
- 前端只执行 `base_expression + merged_params`

这套方案更适合多个 Live2D 模型共用一套引擎，同时保留每个模型自己的表达资产与参数能力。
