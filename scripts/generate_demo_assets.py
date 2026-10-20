import asyncio
import os
import shutil
import subprocess
from playwright.async_api import async_playwright

VIDEO_DIR = "/Users/weineoliveira/platina-ai/docs/media"
RECORDING_DIR = os.path.join(VIDEO_DIR, "raw_recordings")

os.makedirs(RECORDING_DIR, exist_ok=True)

FFMPEG_BIN = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"

async def type_and_send(page, text: str, typing_delay: int = 18):
    await page.click("#userInput")
    for char in text:
        await page.keyboard.type(char, delay=typing_delay)
        await asyncio.sleep(0.004)
    await asyncio.sleep(0.3)
    await page.click("#sendBtn")

async def record_demo():
    print("🎬 Starting Playwright browser demo recorder...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            record_video_dir=RECORDING_DIR,
            record_video_size={"width": 1280, "height": 800},
            viewport={"width": 1280, "height": 800},
            device_scale_factor=2,  # Retina crispness
        )

        page = await context.new_page()

        print("Navigating to http://localhost:3000/ui ...")
        await page.goto("http://localhost:3000/ui")
        await page.wait_for_selector("#chatBox")

        # Ensure fresh state with initial onboarding greeting
        await page.wait_for_selector(".onboarding-chips", timeout=10000)
        print("Onboarding greeting loaded.")
        await asyncio.sleep(1.5)

        # 1. User initiates game session with The Witcher 3: Wild Hunt
        prompt_1 = "The Witcher 3: Wild Hunt"
        print(f"1. User initiates game: '{prompt_1}'")
        await type_and_send(page, prompt_1, typing_delay=22)

        # Wait for agent 1-turn player briefing stream to finish
        print("Waiting for single-turn player status briefing...")
        await page.wait_for_selector(".msg.assistant", timeout=30000)
        await page.wait_for_function(
            "document.getElementById('sendBtn').disabled === false",
            timeout=60000
        )
        print("Player status briefing complete!")
        await asyncio.sleep(2.5)

        # 2. User asks for missable trophies
        prompt_2 = "quais são os troféus missáveis de the witcher 3?"
        print(f"2. User asks: '{prompt_2}'")
        await type_and_send(page, prompt_2, typing_delay=18)

        # Wait for structured missables table & recommendations stream
        print("Waiting for missables response...")
        await asyncio.sleep(1.0)
        await page.wait_for_function(
            "document.getElementById('sendBtn').disabled === false",
            timeout=60000
        )
        print("Missables response complete!")
        await asyncio.sleep(3.0)

        # 3. User asks for deep details walkthrough
        prompt_3 = "sim, me dê os detalhes de cada um desses troféus missáveis"
        print(f"3. User asks follow-up: '{prompt_3}'")
        await type_and_send(page, prompt_3, typing_delay=18)

        # Wait for detailed walkthrough stream
        print("Waiting for deep walkthrough response...")
        await asyncio.sleep(1.5)
        await page.wait_for_function(
            "document.getElementById('sendBtn').disabled === false",
            timeout=60000
        )
        print("Deep walkthrough complete!")
        await asyncio.sleep(3.5)

        # Close page to flush and save video
        video_path = await page.video.path()
        await context.close()
        await browser.close()

        print(f"Raw video saved at: {video_path}")
        return video_path

def convert_to_mp4_and_gif(raw_video_path):
    mp4_out = os.path.join(VIDEO_DIR, "platina-ai-demo.mp4")
    gif_out = os.path.join(VIDEO_DIR, "platina-ai-demo.gif")

    print(f"Converting to high-quality MP4 using {FFMPEG_BIN}...")
    subprocess.run([
        FFMPEG_BIN, "-y",
        "-i", raw_video_path,
        "-c:v", "libx264",
        "-crf", "20",
        "-preset", "slow",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        mp4_out
    ], check=True)

    print(f"Converting to optimized GIF using {FFMPEG_BIN}...")
    # 2-pass palettegen filter for crisp text without banding
    subprocess.run([
        FFMPEG_BIN, "-y",
        "-i", raw_video_path,
        "-vf", "fps=14,scale=960:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse=dither=bayer:bayer_scale=3",
        gif_out
    ], check=True)

    print(f"SUCCESS!\nMP4: {mp4_out}\nGIF: {gif_out}")
    return mp4_out, gif_out

if __name__ == "__main__":
    raw_video = asyncio.run(record_demo())
    convert_to_mp4_and_gif(raw_video)