# ComfyUI 图片生成器

## 前置条件

1. ComfyUI 运行在 `127.0.0.1:8188`
2. 从 ComfyUI 导出白板风格工作流为 API 格式，保存到 `<skill-dir>/scripts/workflow_api.json`

## 用法

运行内置脚本：

```bash
python3 <skill-dir>/scripts/generate-image.py "<提示词>" "<宽高比>" "<输出目录>"
```

**注意**：`<skill-dir>` 是 `whiteboard-video-workflow` skill 的绝对路径，由主 agent 在 subagent 指令中提供。

**参数：**
1. `prompt`（必填）— 图片生成提示词。支持两种模式：
   - **单张模式**：传入普通字符串，如 `"whiteboard doodle of a lightbulb"`
   - **批量模式**：传入 JSON 编码的字符串数组，如 `'["提示词1","提示词2","提示词3"]'`。每个数组元素对应一张图片，脚本串行生成。
2. `aspect-ratio`（可选，默认值：`"16:9"`）— 图片宽高比（如 `"1:1"`、`"9:16"`、`"16:9"`、`"4:3"`）。
3. `output-dir`（可选，默认值：当前工作目录）— 生成图片的保存目录。

**示例：**

单张生成：
```bash
python3 <skill-dir>/scripts/generate-image.py "whiteboard doodle of a lightbulb" "16:9" "./output"
```

批量生成：
```bash
python3 <skill-dir>/scripts/generate-image.py '["whiteboard doodle of a lightbulb","whiteboard doodle of a flower"]' "16:9" "./output"
```

## 工作流程

1. 验证 `prompt` 不为空。如果缺失，询问用户。
2. 检测 `prompt` 是否为 JSON 数组格式，自动区分单张/批量模式。
3. 使用三个参数运行 `scripts/generate-image.py`。
4. 脚本自动处理：
   - 加载工作流 JSON
   - 查找并更新 CLIPTextEncode 节点（设置提示词）
   - 查找并更新 KSampler/RandomNoise 节点（设置种子）
   - 发送 POST /prompt 请求
   - 轮询 GET /history/{prompt_id} 等待完成
   - 从 outputs 中提取图片信息
   - 下载最大分辨率图片
   - 重试机制：失败时最多重试 3 次（指数退避）
5. 向用户报告保存的文件路径。

## 批量模式说明

- 当 `prompt` 参数是 JSON 字符串数组时自动进入批量模式
- 串行执行，每张图片独立
- 单张失败不影响其他图片
- 输出文件名格式：`comfyui_<序号>_<时间戳>_seed<种子>.png`
- 执行结束后输出汇总信息：成功数和失败数
- 脚本输出的最后一行以 `__RESULTS__` 前缀加上 JSON 数组，包含每张图片的保存路径或错误信息

## 资源文件

- `scripts/generate-image.py` — 独立的 Python 脚本，处理完整的生成-轮询-下载流程，支持单张和批量模式
- `scripts/workflow_api.json` — ComfyUI 导出的白板风格工作流（需用户导出）
