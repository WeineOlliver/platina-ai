import asyncio
import os
import subprocess
from playwright.async_api import async_playwright

VIDEO_DIR = "/Users/weineoliveira/platina-ai/docs/media"
RECORDING_DIR = os.path.join(VIDEO_DIR, "raw_recordings")

os.makedirs(RECORDING_DIR, exist_ok=True)

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
        await asyncio.sleep(1)

        # Set game input explicitly to The Witcher 3: Wild Hunt
        print("Setting game input to The Witcher 3: Wild Hunt...")
        await page.fill("#gameInput", "The Witcher 3: Wild Hunt")
        await page.evaluate("handleGameChange('The Witcher 3: Wild Hunt')")
        await asyncio.sleep(1)

        # 1. Type prompt about Witcher 3 missables
        prompt_1 = "quais são os troféus missáveis de the witcher 3 e o que preciso saber sobre eles?"
        print(f"Typing: {prompt_1}")
        await page.click("#userInput")
        for char in prompt_1:
            await page.keyboard.type(char, delay=20)
            await asyncio.sleep(0.005)

        await asyncio.sleep(0.5)
        print("Sending prompt 1...")
        await page.click("#sendBtn")

        # Wait for the table or message to appear and stream to finish (send button re-enabled)
        print("Waiting for agent streaming to complete...")
        await page.wait_for_selector(".msg.assistant", timeout=45000)
        await page.wait_for_function("document.getElementById('sendBtn').disabled === false", timeout=60000)
        print("First response complete!")
        await asyncio.sleep(3.5)

        # 2. Type follow-up prompt
        prompt_2 = "sim, me dê os detalhes de cada um desses troféus missáveis"
        print(f"Typing follow-up: {prompt_2}")
        await page.click("#userInput")
        for char in prompt_2:
            await page.keyboard.type(char, delay=20)
            await asyncio.sleep(0.005)

        await asyncio.sleep(0.5)
        print("Sending follow-up...")
        await page.click("#sendBtn")

        # Wait for second stream to finish
        print("Waiting for follow-up response...")
        await asyncio.sleep(2)
        await page.wait_for_function("document.getElementById('sendBtn').disabled === false", timeout=60000)
        print("Follow-up response complete!")
        await asyncio.sleep(4)

        # Close page to save video
        video_path = await page.video.path()
        await context.close()
        await browser.close()

        print(f"Raw video saved at: {video_path}")
        return video_path

def convert_to_mp4_and_gif(raw_video_path):
    mp4_out = os.path.join(VIDEO_DIR, "platina-ai-demo.mp4")
    gif_out = os.path.join(VIDEO_DIR, "platina-ai-demo.gif")

    print("Converting to high-quality MP4...")
    subprocess.run([
        "/opt/homebrew/bin/ffmpeg", "-y",
        "-i", raw_video_path,
        "-c:v", "libx264",
        "-crf", "20",
        "-preset", "slow",
        "-pix_fmt", "yuv420p",
        mp4_out
    ], check=True)

    print("Converting to optimized GIF...")
    # 2-pass palettegen filter for crisp text without banding
    subprocess.run([
        "/opt/homebrew/bin/ffmpeg", "-y",
        "-i", raw_video_path,
        "-vf", "fps=14,scale=960:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=128[p];[s1][p]paletteuse=dither=bayer:bayer_scale=3",
        gif_out
    ], check=True)

    print(f"SUCCESS!\nMP4: {mp4_out}\nGIF: {gif_out}")
    return mp4_out, gif_out

if __name__ == "__main__":
    raw_video = asyncio.run(record_demo())
    convert_to_mp4_and_gif(raw_video)
