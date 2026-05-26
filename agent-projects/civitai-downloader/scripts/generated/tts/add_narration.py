"""
AI 短视频配音 + 合成工具（内网 TTS 版）
========================================
使用内网 spark-tts 模型生成中文配音，ffmpeg 合成最终短片。
遵循全局规则：优先本地/离线 TTS，保证最终效果可控。

用法：
  python add_narration.py --video 视频.mp4 --text "旁白文本"
  python add_narration.py --video 视频.mp4 --text "旁白文本" --speaker male1 --speed 0.9
  python add_narration.py --video 视频.mp4 --audio 已有配音.wav  # 跳过 TTS，直接合成
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

import requests

# ---- 内网 TTS 服务 ----
TTS_SERVER = "http://192.168.88.112:18081"
TTS_MODEL = "spark-tts"
SMB_PREFIX = r"\\192.168.88.112\d$"

# ---- 输出目录 ----
OUTPUT_DIR = Path(r"D:\ComfyUI-aki-v3\agent-projects\civitai-downloader\runtime\tts")

# ---- spark-tts 单次文本上限（中文字符） ----
CHUNK_MAX_CHARS = 45


def tts_api_call(text: str, speaker: str = "male1", speed: float = 1.0,
                 timeout: int = 120) -> dict:
    """调用内网 TTS Gateway 同步接口"""
    body = {"model": TTS_MODEL, "text": text, "speaker": speaker, "speed": speed}
    resp = requests.post(f"{TTS_SERVER}/tts", json=body, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def server_path_to_smb(server_path: str) -> str:
    """将 TTS 服务器本地路径转为 SMB 路径"""
    return server_path.replace("D:", SMB_PREFIX, 1)


def download_audio(server_path: str, local_path: Path) -> Path:
    """通过 SMB 从 TTS 服务器下载音频文件"""
    smb_path = server_path_to_smb(server_path)
    local_path.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(10):
        if Path(smb_path).exists():
            break
        time.sleep(0.5)
    subprocess.run(
        ["copy", smb_path, str(local_path)],
        shell=True, check=True, capture_output=True,
    )
    return local_path


def split_text(text: str, max_chars: int = CHUNK_MAX_CHARS) -> list[str]:
    """将长文本按句子边界分段，每段不超过 max_chars 字符"""
    if len(text) <= max_chars:
        return [text]
    chunks = []
    delimiters = "。！？；，、\n"
    current = ""
    for char in text:
        current += char
        if char in delimiters and len(current) >= max_chars * 0.6:
            chunks.append(current)
            current = ""
        elif len(current) >= max_chars:
            chunks.append(current)
            current = ""
    if current.strip():
        chunks.append(current)
    merged = []
    for c in chunks:
        if merged and len(c) < 10:
            merged[-1] += c
        else:
            merged.append(c)
    return merged


def generate_tts(text: str, speaker: str, speed: float) -> Path:
    """用内网 spark-tts 生成配音，长文本自动分段"""
    chunks = split_text(text)
    sizes = [f"{len(c)}字" for c in chunks]
    print(f"文本分 {len(chunks)} 段: {sizes}")
    audio_files = []
    for i, chunk in enumerate(chunks):
        preview = chunk[:30] + "..." if len(chunk) > 30 else chunk
        print(f"  TTS 第 {i+1}/{len(chunks)} 段: \"{preview}\"")
        result = tts_api_call(chunk, speaker=speaker, speed=speed)
        if result.get("status") != "succeeded":
            raise RuntimeError(f"TTS 失败: {result}")
        local_path = OUTPUT_DIR / f"chunk_{i:03d}.wav"
        download_audio(result["audio_path"], local_path)
        print(f"    已保存: {local_path.name} ({result['duration_sec']:.1f}s)")
        audio_files.append(local_path)
    if len(audio_files) == 1:
        return audio_files[0]
    merged_path = OUTPUT_DIR / "narration_merged.wav"
    concat_list = OUTPUT_DIR / "_concat_list.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for af in audio_files:
            f.write(f"file '{af.as_posix()}'\n")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
         "-c", "copy", str(merged_path)],
        check=True, capture_output=True,
    )
    print(f"  已拼接 {len(audio_files)} 段 -> {merged_path}")
    return merged_path


def merge_audio_video(video_path: Path, audio_path: Path, output_path: Path,
                      loop_video: bool = True) -> Path:
    """用 ffmpeg 将音频与视频合成"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y"]
    if loop_video:
        cmd += ["-stream_loop", "-1"]
    cmd += ["-i", str(video_path), "-i", str(audio_path)]
    encoders_try = ["h264_nvenc", "libopenh264"]
    encoder = "libopenh264"
    result = subprocess.run(["ffmpeg", "-encoders"], capture_output=True, text=True)
    for enc in encoders_try:
        if enc in result.stdout:
            encoder = enc
            break
    cmd += ["-c:v", encoder, "-preset", "p1" if "nvenc" in encoder else "fast"]
    if "nvenc" in encoder:
        cmd += ["-cq", "23"]
    else:
        cmd += ["-crf", "23"]
    cmd += [
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100",
        "-shortest", "-map", "0:v:0", "-map", "1:a:0",
        str(output_path),
    ]
    subprocess.run(cmd, check=True)
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="AI 短视频配音 + 合成工具（内网 spark-tts）"
    )
    parser.add_argument("--video", required=True, help="输入视频路径")
    parser.add_argument("--text", default="", help="旁白文本")
    parser.add_argument("--speaker", default="male1", help="spark-tts 音色")
    parser.add_argument("--speed", type=float, default=1.0, help="语速 (0.5~2.0)")
    parser.add_argument("--audio", default="", help="已有配音文件（跳过 TTS）")
    parser.add_argument("--output", default="", help="输出视频路径")
    parser.add_argument("--no-loop", action="store_true", help="视频不循环")
    args = parser.parse_args()

    video_path = Path(args.video)
    if not video_path.exists():
        print(f"错误：视频文件不存在 - {video_path}")
        sys.exit(1)

    tts_available = False
    try:
        health = requests.get(f"{TTS_SERVER}/healthz", timeout=5).json()
        loaded = health.get("loaded_models", [])
        print(f"TTS 服务: {health.get('status')}, 已加载: {loaded}")
        tts_available = True
    except Exception as e:
        print(f"警告：TTS 服务不可达 ({e})")

    if args.audio:
        audio_path = Path(args.audio)
        if not audio_path.exists():
            print(f"错误：音频文件不存在 - {audio_path}")
            sys.exit(1)
        print(f"使用已有配音: {audio_path}")
    elif args.text:
        if not tts_available:
            print("错误：TTS 服务不可用，请使用 --audio 指定已有配音文件")
            sys.exit(1)
        print(f"音色: {args.speaker}, 语速: {args.speed}")
        preview = args.text[:60] + "..." if len(args.text) > 60 else args.text
        print(f"文本 ({len(args.text)}字): \"{preview}\"")
        audio_path = generate_tts(args.text, args.speaker, args.speed)
        print(f"配音完成: {audio_path}")
    else:
        print("错误：需要 --text 或 --audio 参数")
        sys.exit(1)

    if args.output:
        out_path = Path(args.output)
    else:
        stem = video_path.stem
        out_path = OUTPUT_DIR / f"{stem}_narrated.mp4"

    print(f"合成中...")
    merge_audio_video(video_path, audio_path, out_path, loop_video=not args.no_loop)
    size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"完成! {out_path} ({size_mb:.1f}MB)")


if __name__ == "__main__":
    main()
