import asyncio
import edge_tts

async def main():
    text = "深海之中，一只发光的水母正在优雅地漂浮，它的触手散发着迷人的蓝色和紫色生物荧光。"
    output = r"D:\ComfyUI-aki-v3\agent-projects\civitai-downloader\runtime\tts\edge_zh_test.mp3"
    communicate = edge_tts.Communicate(text, "zh-CN-XiaoxiaoNeural", rate="+0%")
    await communicate.save(output)
    print(f"已生成: {output}")

asyncio.run(main())
