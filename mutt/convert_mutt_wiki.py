#!/usr/bin/env python3
"""
Use Playwright to generate a PDF of the Mutt manual from:
http://www.mutt.org/doc/manual/
"""

import sys
from playwright.sync_api import sync_playwright

def main():
    url = "http://www.mutt.org/doc/manual/"
    output_pdf = "mutt-manual.pdf"

    # Optional: check command-line args if you want custom URL or PDF name
    # e.g.: python mutt_to_pdf.py https://example.com docs.pdf
    if len(sys.argv) > 1:
        url = sys.argv[1]
    if len(sys.argv) > 2:
        output_pdf = sys.argv[2]

    print(f"Generating PDF from: {url}")
    print(f"Output file: {output_pdf}")

    with sync_playwright() as p:
        # Launch headless Chromium
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Go to the single-page Mutt manual
        page.goto(url, wait_until="networkidle")

        # Optional: You might want to adjust margins or set scale below
        page.pdf(
            path=output_pdf,
            format="A4",          # or "Letter"
            print_background=True, # Ensures background colors/images
            margin={
                "top": "15mm",
                "bottom": "15mm",
                "left": "10mm",
                "right": "10mm"
            }
            # scale=0.9,          # Optionally shrink or enlarge the page
        )

        browser.close()

    print("Done! PDF saved.")

if __name__ == "__main__":
    main()
