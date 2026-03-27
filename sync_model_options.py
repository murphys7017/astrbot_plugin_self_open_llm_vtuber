#!/usr/bin/env python3
"""
同步 model_dict.json 中的模型列表到 _conf_schema.json 的下拉选项。

使用方法:
    python sync_model_options.py
"""

import json
from pathlib import Path

PLUGIN_DIR = Path(__file__).parent
MODEL_DICT_PATH = PLUGIN_DIR / "live2ds" / "model_dict.json"
CONF_SCHEMA_PATH = PLUGIN_DIR / "_conf_schema.json"


def main():
    print("同步模型选项...")
    print(f"模型字典: {MODEL_DICT_PATH}")
    print(f"配置模式: {CONF_SCHEMA_PATH}")

    # 读取 model_dict.json
    if not MODEL_DICT_PATH.exists():
        print(f"错误: {MODEL_DICT_PATH} 不存在")
        return 1

    with open(MODEL_DICT_PATH, "r", encoding="utf-8") as f:
        model_dict = json.load(f)

    if not isinstance(model_dict, list):
        print(f"错误: {MODEL_DICT_PATH} 应该是 JSON 数组")
        return 1

    # 提取模型名称
    model_names = []
    for item in model_dict:
        if isinstance(item, dict) and "name" in item:
            name = item["name"].strip()
            if name:
                model_names.append(name)

    if not model_names:
        print("警告: 未找到有效的模型名称")
        return 1

    print(f"找到 {len(model_names)} 个模型: {', '.join(model_names)}")

    # 读取并更新 _conf_schema.json
    if not CONF_SCHEMA_PATH.exists():
        print(f"错误: {CONF_SCHEMA_PATH} 不存在")
        return 1

    with open(CONF_SCHEMA_PATH, "r", encoding="utf-8") as f:
        conf_schema = json.load(f)

    if (
        "live2d_model_name" not in conf_schema
        or not isinstance(conf_schema["live2d_model_name"], dict)
    ):
        print("错误: _conf_schema.json 中找不到 live2d_model_name 配置")
        return 1

    old_options = conf_schema["live2d_model_name"].get("options", [])
    conf_schema["live2d_model_name"]["options"] = model_names

    # 如果默认值不在新列表中，使用第一个模型作为默认值
    default_name = conf_schema["live2d_model_name"].get("default")
    if default_name not in model_names and model_names:
        conf_schema["live2d_model_name"]["default"] = model_names[0]
        print(f"更新默认模型为: {model_names[0]}")

    # 写回 _conf_schema.json
    with open(CONF_SCHEMA_PATH, "w", encoding="utf-8") as f:
        json.dump(conf_schema, f, ensure_ascii=False, indent=2)

    print(f"更新完成! 选项从 {old_options} 变为 {model_names}")
    print("请重启 AstrBot 或刷新配置页面以查看更改。")
    return 0


if __name__ == "__main__":
    exit(main())
