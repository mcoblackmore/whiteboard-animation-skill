#!/usr/bin/env python3
"""
ComfyUI 图片生成器 - 重构版本

通过调用本地 ComfyUI REST API 生成白板风格图片。

用法:
    python generate-image.py "<prompt>" [aspect_ratio] [output_dir]
    python generate-image.py '["prompt1", "prompt2"]' [aspect_ratio] [output_dir]  # 批量模式

前置条件:
    1. ComfyUI 运行在 127.0.0.1:8188
    2. 从 ComfyUI 导出白板风格工作流为 API 格式，保存到本脚本同目录的 workflow_api.json
"""

import json
import os
import random
import sys
import time
import traceback
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from banana_prompt_template import whiteboard_prompt_template
except ImportError:
    whiteboard_prompt_template = ""

COMFYUI_SERVER = "127.0.0.1:8188"
WORKFLOW_JSON = str(Path(__file__).resolve().parent / "workflow_api.json")
TIMEOUT_SECONDS = 300
CHECK_INTERVAL = 1
MAX_RETRIES = 3


class RetryableError(Exception):
    def __init__(self, message, *, is_rate_limit=False):
        super().__init__(message)
        self.is_rate_limit = is_rate_limit


def log(message, level="INFO"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    prefixes = {
        "INFO": "[INFO]",
        "OK": "[OK]",
        "WARN": "[WARN]",
        "ERROR": "[ERROR]",
        "PROGRESS": "[PROGRESS]",
    }
    prefix = prefixes.get(level, "[INFO]")
    print(f"{timestamp} {prefix} {message}")
    sys.stdout.flush()


def check_workflow():
    if not os.path.exists(WORKFLOW_JSON):
        log(f"工作流文件不存在: {WORKFLOW_JSON}", "ERROR")
        print("\n请按以下步骤导出工作流:")
        print("  1. 在 ComfyUI 中打开白板风格工作流")
        print("  2. 点击右上角菜单 (三个点)")
        print("  3. 选择 'Save (API Format)' 或 '保存(API格式)'")
        print(f"  4. 保存到: {WORKFLOW_JSON}")
        raise FileNotFoundError(WORKFLOW_JSON)


def load_workflow():
    check_workflow()
    with open(WORKFLOW_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def send_prompt(workflow):
    data = json.dumps({"prompt": workflow}).encode("utf-8")
    req = urllib.request.Request(
        f"http://{COMFYUI_SERVER}/prompt",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for_completion(prompt_id, timeout=TIMEOUT_SECONDS):
    start_time = time.time()
    last_status = None

    while True:
        elapsed = time.time() - start_time
        if elapsed > timeout:
            raise TimeoutError(f"生成超时 (>{timeout}秒)")

        try:
            with urllib.request.urlopen(
                f"http://{COMFYUI_SERVER}/history/{prompt_id}", timeout=10
            ) as response:
                history = json.loads(response.read().decode("utf-8"))
                if prompt_id in history:
                    return history[prompt_id]

                if int(elapsed) % 5 == 0 and int(elapsed) != last_status:
                    last_status = int(elapsed)
                    log(f"等待中... {int(elapsed)}秒", "PROGRESS")

        except urllib.error.HTTPError as e:
            if e.code == 404:
                pass
            else:
                raise
        except Exception as e:
            log(f"检查状态出错: {e}", "WARN")

        time.sleep(CHECK_INTERVAL)


def get_images_from_history(history):
    images = []
    outputs = history.get("outputs", {})
    for node_id, node_output in outputs.items():
        if "images" in node_output:
            for img in node_output["images"]:
                images.append(
                    {
                        "filename": img["filename"],
                        "subfolder": img.get("subfolder", ""),
                        "type": img.get("type", "output"),
                    }
                )
    return images


def download_image(img_info, save_path):
    params = urllib.parse.urlencode(img_info)
    url = f"http://{COMFYUI_SERVER}/view?{params}"
    with urllib.request.urlopen(url, timeout=60) as response:
        with open(save_path, "wb") as f:
            f.write(response.read())
    return save_path


def find_and_update_workflow(workflow_template, positive_prompt, seed):
    workflow = json.loads(json.dumps(workflow_template))

    found_prompt = False
    found_seed = False

    for node_id, node in workflow.items():
        class_type = node.get("class_type", "").lower()
        inputs = node.get("inputs", {})

        if "clip" in class_type and "textencode" in class_type:
            if "text" in inputs:
                inputs["text"] = positive_prompt
                found_prompt = True

        if class_type in ["ksampler", "randomnoise"]:
            for key in ["seed", "noise_seed"]:
                if key in inputs:
                    inputs[key] = seed
                    found_seed = True
                    break

    if not found_prompt:
        log("警告: 未找到提示词节点", "WARN")
    if not found_seed:
        log("警告: 未找到种子节点", "WARN")

    return workflow


def generate_single(index, total, workflow_template, prompt, output_dir, aspect_ratio="16:9"):
    tag = f"[{index}/{total}] " if total > 1 else ""

    log(f"{tag}生成图片...")
    log(f"{tag}提示词: {prompt[:80]}..." if len(prompt) > 80 else f"{tag}提示词: {prompt}")

    seed = random.randint(1, 999999999)
    log(f"{tag}种子: {seed}")

    workflow = find_and_update_workflow(workflow_template, prompt, seed)

    log(f"{tag}发送请求...")
    try:
        response = send_prompt(workflow)
    except Exception as e:
        raise RetryableError(f"{tag}发送请求失败: {e}")

    prompt_id = response.get("prompt_id")
    if not prompt_id:
        raise RetryableError(f"{tag}未获取到任务ID")

    log(f"{tag}任务ID: {prompt_id}")

    log(f"{tag}等待生成完成 (超时: {TIMEOUT_SECONDS}秒)...")
    try:
        history = wait_for_completion(prompt_id)
    except TimeoutError as e:
        raise RetryableError(f"{tag}{e}")

    images = get_images_from_history(history)
    if not images:
        raise RetryableError(f"{tag}生成完成但未找到图片")

    log(f"{tag}找到 {len(images)} 张图片", "OK")

    saved_paths = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    largest_img = None
    largest_size = 0

    for img_info in images:
        params = urllib.parse.urlencode(img_info)
        url = f"http://{COMFYUI_SERVER}/view?{params}"
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                img_data = response.read()
                img_size = len(img_data)
                if img_size > largest_size:
                    largest_size = img_size
                    largest_img = {"info": img_info, "data": img_data}
        except Exception as e:
            log(f"{tag}下载图片失败: {e}", "WARN")
            continue

    if largest_img:
        filename = f"comfyui_{index:04d}_{timestamp}_seed{seed}.png"
        save_path = os.path.join(output_dir, filename)
        with open(save_path, "wb") as f:
            f.write(largest_img["data"])
        size_mb = largest_size / 1024 / 1024
        log(f"{tag}已保存: {filename} ({size_mb:.2f} MB)", "OK")
        saved_paths.append(save_path)
    else:
        img_info = images[0]
        filename = f"comfyui_{index:04d}_{timestamp}_seed{seed}.png"
        save_path = os.path.join(output_dir, filename)
        download_image(img_info, save_path)
        log(f"{tag}已保存: {filename}", "OK")
        saved_paths.append(save_path)

    return saved_paths


def run_batch(prompts, output_dir, aspect_ratio="16:9"):
    print("\n" + "=" * 60)
    log("ComfyUI 图片生成器")
    print("=" * 60)

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    print(f"\n配置:")
    print(f"  服务器: {COMFYUI_SERVER}")
    print(f"  工作流: {WORKFLOW_JSON}")
    print(f"  输出目录: {output_dir}")
    print(f"  生成数量: {len(prompts)}")
    print("=" * 60 + "\n")

    workflow_template = load_workflow()
    log("工作流加载成功", "OK")

    all_results = []
    success_count = 0
    failed_count = 0
    start_time = time.time()

    for i, prompt in enumerate(prompts):
        full_prompt = whiteboard_prompt_template + prompt if whiteboard_prompt_template else prompt

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                results = generate_single(
                    i + 1, len(prompts), workflow_template, full_prompt, output_dir, aspect_ratio
                )
                all_results.extend(results)
                success_count += 1
                break
            except Exception as e:
                log(f"[{i + 1}/{len(prompts)}] 生成失败 (尝试 {attempt}/{MAX_RETRIES}): {e}", "ERROR")
                if attempt == MAX_RETRIES:
                    failed_count += 1
                    traceback.print_exc()
                else:
                    delay = 3 * (2 ** (attempt - 1))
                    log(f"等待 {delay:.1f} 秒后重试...")
                    time.sleep(delay)

        if i < len(prompts) - 1:
            time.sleep(0.5)

    total_time = time.time() - start_time
    print("\n" + "=" * 60)
    log("批量生成完成!")
    print(f"  成功: {success_count}/{len(prompts)}")
    print(f"  失败: {failed_count}/{len(prompts)}")
    print(f"  总耗时: {total_time:.1f} 秒")
    print(f"  平均: {total_time / max(success_count, 1):.1f} 秒/张")
    print(f"  保存位置: {output_dir}")
    print("=" * 60 + "\n")

    return all_results


def main():
    args = sys.argv[1:]
    if len(args) < 1:
        print("用法:")
        print("  python generate-image.py \"<prompt>\" [aspect_ratio] [output_dir]")
        print("  python generate-image.py '[\"prompt1\", \"prompt2\"]' [aspect_ratio] [output_dir]  # 批量模式")
        sys.exit(1)

    prompt_arg = args[0]
    aspect_ratio = args[1] if len(args) > 1 else "16:9"
    output_dir = args[2] if len(args) > 2 else os.getcwd()

    if not prompt_arg.strip():
        log("错误: prompt 不能为空", "ERROR")
        sys.exit(1)

    prompts = None
    try:
        parsed = json.loads(prompt_arg)
        if isinstance(parsed, list) and len(parsed) > 0 and isinstance(parsed[0], str):
            prompts = parsed
    except (json.JSONDecodeError, ValueError):
        pass
    if not prompts:
        prompts = [prompt_arg]

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    try:
        results = run_batch(prompts, output_dir, aspect_ratio)
    except FileNotFoundError:
        sys.exit(1)
    except Exception as e:
        log(f"错误: {e}", "ERROR")
        traceback.print_exc()
        sys.exit(1)

    succeeded = [r for r in results if os.path.exists(r)]
    failed = len(prompts) - len(succeeded)

    print(f"\n__RESULTS__{json.dumps(results)}")


if __name__ == "__main__":
    main()
