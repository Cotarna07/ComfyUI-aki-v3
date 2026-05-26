import asyncio
import edge_tts

async def main():
    voices = await edge_tts.VoicesManager.create()
    zh_voices = [v for v in voices.voices if 'zh' in v['Locale']]
    for v in zh_voices[:15]:
        print(f"{v['ShortName']:35s} {v['Locale']:10s} {v['FriendlyName']}")

asyncio.run(main())
