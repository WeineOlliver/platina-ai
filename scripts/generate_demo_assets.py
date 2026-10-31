import asyncio
import os
import shutil
import subprocess
from playwright.async_api import async_playwright

VIDEO_DIR = "/Users/weineoliveira/platina-ai/docs/media"
RECORDING_DIR = os.path.join(VIDEO_DIR, "raw_recordings")

os.makedirs(RECORDING_DIR, exist_ok=True)

FFMPEG_BIN = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"

async def type_and_send(page, text: str, typing_delay: int = 12):
    await page.click("#userInput")
    for char in text:
        await page.keyboard.type(char, delay=typing_delay)
        await asyncio.sleep(0.002)
    await asyncio.sleep(0.2)
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

        print("Navigating to http://localhost:3001/ui ...")
        await page.goto("http://localhost:3001/ui")
        await page.wait_for_selector("#chatBox")

        # 1. Wait for page load and toggle to English mode
        print("Checking language toggle button...")
        btn_lang = await page.wait_for_selector("#btnLangToggle", timeout=10000)
        btn_text = (await btn_lang.inner_text()).strip()
        print(f"Current toggle button text: '{btn_text}'")
        if "EN" in btn_text:
            await asyncio.sleep(0.4)
            print("Clicking #btnLangToggle to switch UI to English...")
            await btn_lang.click()
            await asyncio.sleep(0.5)

        # 2. Verify English welcome message appears
        welcome_el = await page.wait_for_selector(".msg.assistant .content", timeout=5000)
        welcome_text = await welcome_el.inner_text()
        print(f"Welcome message displayed:\n{welcome_text}")
        assert "Hello, Trophy Hunter! 🏆" in welcome_text, f"Unexpected welcome: {welcome_text}"
        assert "Which game would you like to platinum today?" in welcome_text, f"Unexpected subtitle: {welcome_text}"

        # 3. Click recommendation chip for 'The Witcher 3: Wild Hunt'
        await page.wait_for_selector(".onboarding-chips", timeout=5000)
        print("Clicking recommendation chip for 'The Witcher 3: Wild Hunt'...")
        await asyncio.sleep(0.4)
        chip = page.locator(".chip-btn", has_text="The Witcher 3: Wild Hunt")
        await chip.click()

        # 4. Wait for game roadmap overview
        print("Waiting for game overview & roadmap...")
        await asyncio.sleep(0.5)
        await page.wait_for_function(
            "document.getElementById('sendBtn').disabled === false",
            timeout=60000
        )
        print("Game overview complete!")
        await asyncio.sleep(1.8)

        # 5. Type and send missables question in English
        prompt_2 = "Which missable trophies should I watch out for in The Witcher 3?"
        print(f"User asks: '{prompt_2}'")
        await type_and_send(page, prompt_2, typing_delay=12)

        # Wait for structured missables table & recommendations stream
        print("Waiting for missables response...")
        await asyncio.sleep(0.5)
        await page.wait_for_function(
            "document.getElementById('sendBtn').disabled === false",
            timeout=60000
        )
        print("Missables response complete!")
        await asyncio.sleep(2.0)

        # 6. Type and send step-by-step walkthrough question in English
        prompt_3 = "How to unlock the Card Collector trophy step by step?"
        print(f"User asks follow-up: '{prompt_3}'")
        await type_and_send(page, prompt_3, typing_delay=12)

        # Wait for deep walkthrough stream
        print("Waiting for deep walkthrough response...")
        await asyncio.sleep(0.5)
        await page.wait_for_function(
            "document.getElementById('sendBtn').disabled === false",
            timeout=60000
        )
        print("Deep walkthrough complete!")
        await asyncio.sleep(2.2)

        # Close page to flush and save video
        video_path = await page.video.path()
        await context.close()
        await browser.close()

        print(f"Raw video saved at: {video_path}")
        return video_path

def convert_to_mp4_and_gif(raw_video_path):
    mp4_out = os.path.join(VIDEO_DIR, "platina-ai-demo.mp4")
    gif_out = os.path.join(VIDEO_DIR, "platina-ai-demo.gif")
    gif_light_out = os.path.join(VIDEO_DIR, "platina-ai-demo-light.gif")

    print(f"Converting to high-quality MP4 using {FFMPEG_BIN}...")
    subprocess.run([
        FFMPEG_BIN, "-y",
        "-i", raw_video_path,
        "-c:v", "libx264",
        "-crf", "22",
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
        "-vf", "fps=10,scale=800:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=96[p];[s1][p]paletteuse=dither=bayer:bayer_scale=3",
        gif_out
    ], check=True)

    print(f"Converting to lightweight GIF using {FFMPEG_BIN}...")
    subprocess.run([
        FFMPEG_BIN, "-y",
        "-i", raw_video_path,
        "-vf", "fps=6,scale=560:-1:flags=lanczos,split[s0][s1];[s0]palettegen=max_colors=48[p];[s1][p]paletteuse=dither=bayer:bayer_scale=3",
        gif_light_out
    ], check=True)

    print(f"SUCCESS!\nMP4: {mp4_out} ({os.path.getsize(mp4_out)} bytes)\nGIF: {gif_out} ({os.path.getsize(gif_out)} bytes)\nLight GIF: {gif_light_out} ({os.path.getsize(gif_light_out)} bytes)")
    return mp4_out, gif_out, gif_light_out

if __name__ == "__main__":
    raw_video = asyncio.run(record_demo())
    convert_to_mp4_and_gif(raw_video)
