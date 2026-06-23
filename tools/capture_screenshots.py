"""Capture screenshots of key pages for README."""
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8001"
OUT = Path(__file__).parent.parent / "docs"

def main():
    OUT.mkdir(exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 800}, device_scale_factor=2)

        # Landing page
        page.goto(BASE)
        page.wait_for_timeout(500)
        page.screenshot(path=str(OUT / "landing.png"))
        print("Captured landing.png")

        # Submit user_service sample and get review
        page.click("text=User Service")
        page.wait_for_timeout(300)
        page.click("#submit-btn")
        page.wait_for_url("**/review/**", timeout=15000)
        page.wait_for_timeout(500)
        page.screenshot(path=str(OUT / "review.png"), full_page=True)
        print("Captured review.png")

        # Scroll to show conflict section
        page.evaluate("window.scrollTo(0, 400)")
        page.wait_for_timeout(300)
        page.screenshot(path=str(OUT / "review_detail.png"))
        print("Captured review_detail.png")

        browser.close()

if __name__ == "__main__":
    main()
