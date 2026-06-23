"""Capture progress panel demo as GIF using Playwright + Pillow."""
import io
import time
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright

DEMO_HTML = Path(__file__).parent / "progress_demo.html"
OUTPUT = Path(__file__).parent.parent / "docs" / "progress_demo.gif"
DURATION = 19.0
FPS = 10
FRAME_INTERVAL = 1.0 / FPS
VIEWPORT = {"width": 720, "height": 620}

def main():
    OUTPUT.parent.mkdir(exist_ok=True)
    frames = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport=VIEWPORT, device_scale_factor=2)
        page.goto(f"file://{DEMO_HTML.resolve()}")
        page.wait_for_timeout(200)

        start = time.time()
        while time.time() - start < DURATION:
            screenshot = page.screenshot()
            img = Image.open(io.BytesIO(screenshot))
            img = img.resize(VIEWPORT.values(), Image.LANCZOS)
            frames.append(img)
            elapsed = time.time() - start
            wait = max(0, (len(frames) * FRAME_INTERVAL) - elapsed)
            if wait > 0:
                page.wait_for_timeout(int(wait * 1000))

        browser.close()

    print(f"Captured {len(frames)} frames")
    frames[0].save(
        OUTPUT,
        save_all=True,
        append_images=frames[1:],
        duration=int(FRAME_INTERVAL * 1000),
        loop=0,
        optimize=True,
    )
    size_mb = OUTPUT.stat().st_size / 1024 / 1024
    print(f"Saved {OUTPUT} ({size_mb:.1f} MB)")

if __name__ == "__main__":
    main()
