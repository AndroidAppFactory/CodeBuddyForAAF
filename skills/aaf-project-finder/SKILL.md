---
version: 1
name: aaf-project-finder
description: 定位 AAF 相关项目位置。通过 AAF_HOME 环境变量定位 AndroidAppFactory 等项目路径。
---

# AAF Project Finder

## 定位策略

读取环境变量 `AAF_HOME`（在 `~/.zixiekit/.env` 中配置），所有 AAF 项目均位于该目录下：

```
$AAF_HOME/
├── AndroidAppFactory        ← 框架核心（必须存在）
├── AndroidAppFactory-Doc    ← 文档（可选）
├── Template-AAF             ← 完整示例（可选）
├── Template_Android         ← 基础示例（可选）
└── Template-Empty           ← 最简示例（可选）
```

## 执行逻辑

```bash
# 1. 读取 AAF_HOME
AAF_HOME="${AAF_HOME:?错误: 未设置 AAF_HOME 环境变量，请在 ~/.zixiekit/.env 中配置}"

# 2. 验证核心项目
if [ ! -d "$AAF_HOME/AndroidAppFactory" ]; then
    echo "错误: $AAF_HOME/AndroidAppFactory 不存在" >&2
    exit 1
fi

# 3. 返回路径
echo "AndroidAppFactory=$AAF_HOME/AndroidAppFactory"
```

## 返回格式

```
## AAF 项目位置

| 项目 | 路径 | 状态 |
|------|------|------|
| AndroidAppFactory | $AAF_HOME/AndroidAppFactory | ✓ |
| Template-AAF | $AAF_HOME/Template-AAF | ✓ / 不存在 |
| ... | ... | ... |
```

**AndroidAppFactory 找不到 → 报错终止，不继续。**