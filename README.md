# Whiteboard Animation Skills

用于生成白板动画视频的可复用 Agent Skills 仓库。

## 项目结构

```
whiteboard-animation-skill/
├── skills/
│   ├── whiteboard-animation/       # 单图/批量生成白板手绘动画视频
│   │   ├── SKILL.md
│   │   ├── scripts/
│   │   │   ├── generate_whiteboard.py    # 核心生成脚本
│   │   │   ├── batch_generate.py          # 批量生成
│   │   │   └── setup_env.py              # 环境准备
│   │   └── assets/
│   │       └── drawing-hand.png          # 手部素材
│   │
│   └── whiteboard-video-workflow/  # 端到端 SRT→视频工作流
│       ├── SKILL.md
│       ├── references/
│       │   ├── storyboard-parser.md  # SRT 分镜解析指令
│       │   └── image-generator.md    # ComfyUI 图片生成指令
│       └── scripts/
│           ├── generate-storyboard.py    # SRT + groups.json → storyboard.json
│           ├── generate-image.py         # ComfyUI 文生图
│           ├── workflow_helper.py        # init-dirs / gen-prompts / merge-videos
│           ├── banana_prompt_template.py # 白板风格提示词前缀
│           ├── check_env.py              # 环境预检（仅检查 Python 虚拟环境）
│           └── workflow_api.json         # ComfyUI 导出的工作流（需用户导出）
│
├── comfyui_workflow_demo/           # 测试数据目录
└── README.md
```

## 快速开始

### 1. 环境要求

| 依赖 | 说明 |
|------|------|
| Python 3.9+ | 运行环境 |
| ComfyUI | 本地运行在 `127.0.0.1:8188` |
| 工作流 JSON | 从 ComfyUI 导出的白板风格工作流 |

### 2. 导出 ComfyUI 工作流

1. 在 ComfyUI 中打开白板风格工作流
2. 点击右上角菜单 (三个点)
3. 选择 **Save (API Format)** 或 **保存(API格式)**
4. 保存到 `skills/whiteboard-video-workflow/scripts/workflow_api.json`

### 3. 环境预检

```bash
cd skills/whiteboard-video-workflow/scripts
python check_env.py
```

### 4. 端到端工作流（SRT → 视频）

```bash
# 1. 环境预检
python scripts/check_env.py

# 2. 初始化目录
python scripts/workflow_helper.py init-dirs "/path/to/output"

# 3. 生成分镜（需要 AI 辅助生成 groups.json）
python scripts/generate-storyboard.py "/path/to/input.srt" "/path/to/groups.json" "/path/to/storyboard.json"

# 4. 生成提示词
python scripts/workflow_helper.py gen-prompts "/path/to/storyboard.json"

# 5. 批量生成图片（需要先导出 workflow_api.json）
python scripts/generate-image.py '["提示词1", "提示词2"]' "16:9" "/path/to/image/dir"

# 6. 生成视频片段
python scripts/batch_generate.py --images "/path/to/img1.png" ... --durations 5000 ... --output-dir "/path/to/video/dir"

# 7. 合并视频
python scripts/workflow_helper.py merge-videos "/path/to/output" "/path/to/video1.mp4" "/path/to/video2.mp4"
```

## skills 说明

### whiteboard-animation

根据输入的图片生成白板手绘动画视频。

**输入**：单张或多张白板风格图片 + 每张图片对应时长（毫秒）

**输出**：白板手绘动画视频片段

### whiteboard-video-workflow

从 SRT 字幕文件出发，完成分镜生成、图片生成、视频片段生成与最终合并的端到端工作流。

**输入**：SRT 字幕文件

**输出**：完整的白板动画视频

**流程**：
```
SRT → 分镜解析 → 生成 storyboard.json
                          ↓
                    gen-prompts 生成提示词
                          ↓
                    generate-image (ComfyUI) 生成图片
                          ↓
                    batch_generate 生成视频片段
                          ↓
                    merge-videos 合并最终视频
```

## generate-image.py 详解

### 工作原理

```
1. 加载本地 workflow_api.json
2. 查找并更新 CLIPTextEncode 节点（设置提示词）
3. 查找并更新 KSampler/RandomNoise 节点（设置随机种子）
4. POST /prompt → 发送生成任务
5. GET /history/{prompt_id} → 轮询等待完成
6. GET /view?filename=... → 下载最大分辨率图片
```

### 命令行用法

```bash
# 单张生成
python generate-image.py "<prompt>" [aspect_ratio] [output_dir]

# 批量生成（通过 Python 调用 run_batch 函数）
python generate-image.py '["prompt1", "prompt2", "prompt3"]' [aspect_ratio] [output_dir]
```

### 参数说明

| 参数 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| prompt | 是 | - | 提示词文本，或 JSON 数组（批量模式） |
| aspect_ratio | 否 | 16:9 | 图片比例（1:1, 16:9, 9:16, 4:3, 3:4） |
| output_dir | 否 | 当前目录 | 输出目录路径 |

### 配置常量

在脚本头部可修改：

```python
COMFYUI_SERVER = "127.0.0.1:8188"      # ComfyUI 地址
WORKFLOW_JSON = ".../workflow_api.json" # 工作流文件路径
TIMEOUT_SECONDS = 300                   # 单张图片最大等待时间（秒）
MAX_RETRIES = 3                         # 失败重试次数
```

## 工作流 JSON 文件

`workflow_api.json` 需要包含以下节点类型：

| 节点类型 | 说明 | 必须字段 |
|----------|------|----------|
| `CLIPTextEncode` | 文本编码 | `text` |
| `KSampler` 或 `RandomNoise` | 采样器/噪声 | `seed` 或 `noise_seed` |
| `SaveImage` | 图片保存 | - |

**重要**：节点中的 `seed` / `noise_seed` 字段用于脚本自动设置随机种子，每张图片使用不同的种子确保输出不重复。

## 白板风格提示词

`banana_prompt_template.py` 定义了白板风格的提示词前缀：

```python
whiteboard_prompt_template = "Minimal hand-drawn illustration, pure illustration without any text, off-white paper background(#F6F1E3), dark gray sketch lines, orange as the only accent color(#CD6441), lots of negative space, Notion-like doodle aesthetic, faceless round-headed human figure, clean editorial composition, conceptual rather than literal, simple background. Absolutely no text, no words, no letters, no typography, no realism, no 3D, no painterly texture, no high saturation, no complex scene, no photographic detail. The overall mood is restrained, lucid, and emotionally calm. Keep the whole series visually consistent."
```

该模板会自动添加到所有图片提示词前面，确保生成的白板风格图片一致性。

## 常见问题

### Q: 提示 "工作流文件不存在"

确保已从 ComfyUI 导出 API 格式工作流到 `workflow_api.json`。

### Q: 连接失败

检查 ComfyUI 是否运行在 `127.0.0.1:8188`，端口是否正确。

### Q: 生成的图片位置不对

工作流中的 SaveImage 节点会影响 ComfyUI 默认输出目录，脚本会从 `/view` API 获取图片并保存到指定目录。

### Q: 如何使用非默认端口

修改 `generate-image.py` 头部的 `COMFYUI_SERVER`：
```python
COMFYUI_SERVER = "127.0.0.1:8188"  # 改为你的地址:端口
```

### Q: 图片中出现中文乱码

这通常是 ComfyUI 使用的模型对中文支持不好导致的。可尝试：
1. 更换为支持中文的 SD 模型
2. 或在 visualHint 中使用纯英文描述
whiteboard-animation-skill/
├── skills/
│   ├── whiteboard-animation/       # 单图/批量生成白板手绘动画视频
│   │   ├── SKILL.md
│   │   ├── scripts/
│   │   │   ├── generate_whiteboard.py
│   │   │   ├── batch_generate.py
│   │   │   └── setup_env.py
│   │   └── assets/
│   │       └── drawing-hand.png
│   │
│   └── whiteboard-video-workflow/  # 端到端 SRT→视频工作流
│       ├── SKILL.md
│       ├── references/
│       │   ├── storyboard-parser.md  # SRT 分镜解析指令
│       │   └── image-generator.md    # ComfyUI 图片生成指令
│       └── scripts/
│           ├── generate-storyboard.py    # SRT + groups.json → storyboard.json
│           ├── generate-image.py         # ComfyUI 文生图（核心重构脚本）
│           ├── workflow_helper.py        # init-dirs / gen-prompts / merge-videos
│           ├── banana_prompt_template.py # 白板风格提示词前缀
│           └── check_env.py              # 环境预检
│
└── README.md
```

## 快速开始

### 1. 环境要求

| 依赖 | 说明 |
|------|------|
| Python 3.9+ | 运行环境 |
| ComfyUI | 本地运行在 `127.0.0.1:8188` |
| 工作流 JSON | 从 ComfyUI 导出的白板风格工作流 |

### 2. 导出 ComfyUI 工作流

1. 在 ComfyUI 中打开白板风格工作流
2. 点击右上角菜单 (三个点)
3. 选择 **Save (API Format)** 或 **保存(API格式)**
4. 保存到 `skills/whiteboard-video-workflow/scripts/workflow_api.json`

### 3. 测试图片生成

```bash
cd skills/whiteboard-video-workflow/scripts
python generate-image.py "a lightbulb on paper" "16:9" "C:\output\dir"
```

### 4. 端到端工作流（SRT → 视频）

```bash
# 1. 环境预检
python scripts/check_env.py

# 2. 初始化目录
python scripts/workflow_helper.py init-dirs "/path/to/output"

# 3. 生成分镜（需要 AI 辅助生成 groups.json）
python scripts/generate-storyboard.py "/path/to/input.srt" "/path/to/groups.json" "/path/to/storyboard.json"

# 4. 生成提示词
python scripts/workflow_helper.py gen-prompts "/path/to/storyboard.json"

# 5. 批量生成图片（需要先导出 workflow_api.json）
python scripts/generate-image.py '["提示词1", "提示词2"]' "16:9" "/path/to/image/dir"

# 6. 生成视频片段
python scripts/batch_generate.py --images "/path/to/img1.png" ... --durations 5000 ... --output-dir "/path/to/video/dir"

# 7. 合并视频
python scripts/workflow_helper.py merge-videos "/path/to/output" "/path/to/video1.mp4" "/path/to/video2.mp4"
```

## skills 说明

### whiteboard-animation

根据输入的图片生成白板手绘动画视频。

**输入**：单张或多张白板风格图片 + 每张图片对应时长（毫秒）

**输出**：白板手绘动画视频片段

### whiteboard-video-workflow

从 SRT 字幕文件出发，完成分镜生成、图片生成、视频片段生成与最终合并的端到端工作流。

**输入**：SRT 字幕文件

**输出**：完整的白板动画视频

**流程**：
```
SRT → 分镜解析 → 生成 storyboard.json
                          ↓
                    gen-prompts 生成提示词
                          ↓
                    generate-image (ComfyUI) 生成图片
                          ↓
                    batch_generate 生成视频片段
                          ↓
                    merge-videos 合并最终视频
```

## generate-image.py 详解

### 工作原理

```
1. 加载本地 workflow_api.json
2. 查找并更新 CLIPTextEncode 节点（设置提示词）
3. 查找并更新 KSampler/RandomNoise 节点（设置随机种子）
4. POST /prompt → 发送生成任务
5. GET /history/{prompt_id} → 轮询等待完成
6. GET /view?filename=... → 下载最大分辨率图片
```

### 命令行用法

```bash
# 单张生成
python generate-image.py "<提示词>" [aspect_ratio] [output_dir]

# 批量生成
python generate-image.py '["提示词1", "提示词2", "提示词3"]' [aspect_ratio] [output_dir]
```

### 参数说明

| 参数 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| prompt | 是 | - | 提示词文本，或 JSON 数组（批量模式） |
| aspect_ratio | 否 | 16:9 | 图片比例（1:1, 16:9, 9:16, 4:3, 3:4） |
| output_dir | 否 | 当前目录 | 输出目录路径 |

### 输出示例

```
12:34:56 [OK] ComfyUI 图片生成器
============================================================
配置:
  服务器: 127.0.0.1:8188
  工作流: .../workflow_api.json
  输出目录: C:\output\dir
  生成数量: 3
============================================================

12:34:56 [INFO] [1/3] 生成图片...
12:34:56 [INFO] [1/3] 提示词: Minimal hand-drawn illustration, a lightbulb...
12:34:56 [INFO] [1/3] 种子: 123456789
12:34:56 [INFO] [1/3] 发送请求...
12:34:56 [INFO] [1/3] 任务ID: abc123
12:34:56 [INFO] [1/3] 等待生成完成 (超时: 300秒)...
12:35:12 [OK] [1/3] 找到 1 张图片
12:35:12 [OK] [1/3] 已保存: comfyui_0001_20250425_123456_seed123456789.png (7.82 MB)
...

12:35:30 [INFO] 批量生成完成!
  成功: 3/3
  失败: 0/3
  总耗时: 34.2 秒
  平均: 11.4 秒/张
  保存位置: C:\output\dir
```

### 配置常量

在脚本头部可修改：

```python
COMFYUI_SERVER = "127.0.0.1:8188"      # ComfyUI 地址
WORKFLOW_JSON = ".../workflow_api.json" # 工作流文件路径
TIMEOUT_SECONDS = 300                   # 单张图片最大等待时间（秒）
MAX_RETRIES = 3                         # 失败重试次数
```

## 工作流 JSON 文件

`workflow_api.json` 需要包含以下节点类型：

| 节点类型 | 说明 | 必须字段 |
|----------|------|----------|
| `CLIPTextEncode` | 文本编码 | `text` |
| `KSampler` 或 `RandomNoise` | 采样器/噪声 | `seed` 或 `noise_seed` |
| `SaveImage` | 图片保存 | - |

**重要**：节点中的 `seed` / `noise_seed` 字段用于脚本自动设置随机种子，每张图片使用不同的种子确保输出不重复。

## 常见问题

### Q: 提示 "工作流文件不存在"

确保已从 ComfyUI 导出 API 格式工作流到 `workflow_api.json`。

### Q: 连接失败

检查 ComfyUI 是否运行在 `127.0.0.1:8188`，端口是否正确。

### Q: 生成的图片位置不对

工作流中的 SaveImage 节点会影响 ComfyUI 默认输出目录，脚本会从 `/view` API 获取图片并保存到指定目录。

### Q: 如何使用非默认端口

修改 `generate-image.py` 头部的 `COMFYUI_SERVER`：
```python
COMFYUI_SERVER = "127.0.0.1:8188"  # 改为你的地址:端口
```
