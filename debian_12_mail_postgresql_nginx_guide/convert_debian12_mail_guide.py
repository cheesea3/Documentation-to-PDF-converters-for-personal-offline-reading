#!/usr/bin/env python3
"""
Scrape Debian 12 tutorials from server-world.info, remove extra elements,
convert each page to PDF, and optionally merge them.

This version tries very hard not to skip any pages:
  - 5-minute timeouts
  - up to 4 retries
  - waits for DOM content instead of network idle
  - if it still times out on final retry, we do a best-effort PDF

Prerequisites:
  pip install playwright PyPDF2
  playwright install

Usage:
  python serverworld_debian12_to_pdf_v5.py

Author: ChatGPT
"""

import sys
import re
import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError
import PyPDF2

# -------------------------------
# Configuration
# -------------------------------

# The "Debian 12 Download" page is the main entry point
MAIN_URL = "https://www.server-world.info/en/note?os=Debian_12&p=download"

# Whether to merge everything at the end
MERGE_PDFS = True

# Where to save PDFs
OUTPUT_DIR = "serverworld_debian12_tutorials_v5"

# We'll give each page a large timeout (5 minutes).
GOTO_TIMEOUT_MS = 300_000  # 5 minutes

# How many times to retry if a page times out
MAX_RETRIES = 4

# Some CSS selectors to remove
REMOVE_SELECTORS_BASE = [
    "header.header_wrap",
    "div#top-menu",
    "div#footer",
    "div#bann",      # ad area
    "iframe",
    "ins.adsbygoogle",
    "script",
    "style",
    "table[style*='text-align: center; font-size: 12px;']",  # sponsor table
    "#right",        # right pane
    "#bann",         # sponsor ads
]

# On sub-pages we also remove #left (the big nav).
REMOVE_SELECTORS_SUBPAGE = REMOVE_SELECTORS_BASE + ["#left"]

# Additional CSS to hide leftover clutter and style code blocks.
CUSTOM_CSS = """
/* Hide top/bottom clutter if it exists */
#top-menu, #footer, #bann, #right {
    display: none !important;
}
body {
    font-family: "Arial", sans-serif;
    line-height: 1.4;
    font-size: 15px;
    color: #000;
}
table {
    max-width: 100%;
    overflow: auto;
}
img {
    max-width: 100%;
    height: auto;
}

/* Basic styling for code blocks or pre blocks */
pre, code {
    font-family: "Courier New", Consolas, monospace !important;
    background-color: #f5f5f5;
    border: 1px solid #aaa;
    padding: 0.8em;
    border-radius: 4px;
    display: block;
    color: #333;
    overflow-x: auto;
    margin: 1.2em 0;
}
"""

# -------------------------------
# Functions
# -------------------------------

def create_output_dir():
    """Create the output directory if it doesn't exist."""
    out_path = Path(OUTPUT_DIR)
    out_path.mkdir(exist_ok=True, parents=True)
    return out_path

def sanitize_filename(fname: str) -> str:
    """Remove characters that could break filenames."""
    return re.sub(r'[\\/:*?"<>|]', '', fname)

def remove_extras(page, remove_selectors):
    """Remove extraneous DOM elements."""
    for sel in remove_selectors:
        page.evaluate(
            f"""
            () => {{
                const badEls = document.querySelectorAll("{sel}");
                badEls.forEach(el => el.remove());
            }}
            """
        )

def get_all_topic_links(page):
    """
    Parse <div id="left"> .navi and find all links belonging to Debian_12
    Return a list of (url, link_text).
    """
    link_els = page.query_selector_all('#left .navi a')
    all_links = []
    for link_el in link_els:
        href = link_el.get_attribute('href') or ''
        text = link_el.inner_text().strip()
        if 'os=Debian_12' in href:
            abs_url = page.evaluate(f'new URL("{href}", location.href).href')
            all_links.append((abs_url, text))

    # De-duplicate by URL
    unique_links = []
    seen = set()
    for (url, txt) in all_links:
        if url not in seen:
            seen.add(url)
            unique_links.append((url, txt))
    return unique_links

def make_pdf_filename(index, link_text):
    """Create a tidy PDF filename from the link text."""
    index_str = str(index).zfill(3)
    txt = link_text if link_text else "NoTitle"
    txt = sanitize_filename(txt[:60])  # limit length
    return f"{index_str}-{txt}.pdf"

def load_page_with_retries(page, url):
    """
    Attempt up to MAX_RETRIES to goto `url` waiting for DOMContentLoaded.
    Return True if successful, else False.  We will still produce a PDF
    even if after final attempt it times out, but we log an error.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=GOTO_TIMEOUT_MS)
            # Wait a moment for DOM to stabilize:
            time.sleep(2)
            # optionally wait for a main element to appear (some pages are slow):
            page.wait_for_selector("#contents", timeout=60_000)
            return True
        except TimeoutError:
            print(f"  => Timeout while loading {url}. Attempt {attempt}/{MAX_RETRIES} failed.")
            if attempt < MAX_RETRIES:
                print("     Retrying ...")
            else:
                print("     Final attempt also failed; proceeding with partial content.")
                return False

# -------------------------------
# Main Script
# -------------------------------

def main():
    out_dir = create_output_dir()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # 1) Load the main Debian 12 Download page
        print(f"Navigating to main page => {MAIN_URL}")
        try:
            page.goto(MAIN_URL, wait_until="domcontentloaded", timeout=GOTO_TIMEOUT_MS)
            time.sleep(2)
            page.wait_for_selector("#left", timeout=60_000)
        except TimeoutError:
            print(f"[ERROR] Main page timed out even after {GOTO_TIMEOUT_MS} ms. We'll attempt partial PDF anyway.")

        # Remove clutter on the main page but keep #left nav
        remove_extras(page, REMOVE_SELECTORS_BASE)
        page.add_style_tag(content=CUSTOM_CSS)

        # 2) Gather links
        topic_links = get_all_topic_links(page)
        print(f"Found {len(topic_links)} Debian 12 tutorial links in left nav.\n")

        # 3) Save main page PDF (the index)
        pdf_index_path = out_dir / "000-MainIndex.pdf"
        page.pdf(
            path=str(pdf_index_path),
            format="A4",
            print_background=True,
            margin={"top": "15mm", "bottom": "15mm", "left": "10mm", "right": "10mm"},
        )
        print(f"Saved PDF for main index => {pdf_index_path}")

        # We'll collect PDF paths to possibly merge at the end
        pdf_paths = [str(pdf_index_path)]
        index = 1

        # 4) Process each sub-page
        for (url, link_text) in topic_links:
            print(f"[{index}/{len(topic_links)}] Loading => {link_text} => {url}")
            new_page = browser.new_page()

            success = load_page_with_retries(new_page, url)
            # Even if success=False, we proceed, generating a partial PDF from whatever loaded.

            remove_extras(new_page, REMOVE_SELECTORS_SUBPAGE)
            new_page.add_style_tag(content=CUSTOM_CSS)

            # Compose a nice doc title
            raw_title = new_page.title() or link_text
            # Remove trailing brand if present
            page_title = re.sub(r'\s*:\s*Server World.*$', '', raw_title)

            pdf_fname = make_pdf_filename(index, page_title)
            pdf_path = out_dir / pdf_fname

            # Save PDF
            new_page.pdf(
                path=str(pdf_path),
                format="A4",
                print_background=True,
                margin={"top": "15mm", "bottom": "15mm", "left": "10mm", "right": "10mm"},
            )
            print(f"  => saved PDF: {pdf_fname}")
            pdf_paths.append(str(pdf_path))

            new_page.close()
            index += 1

        browser.close()

    # 5) Optionally merge all PDFs
    if MERGE_PDFS and pdf_paths:
        merged_name = "serverworld-debian12-all-in-one_v5.pdf"
        merged_path = Path(out_dir) / merged_name
        print(f"\nMerging {len(pdf_paths)} PDFs into => {merged_name}")

        writer = PyPDF2.PdfWriter()
        for pdf_file in pdf_paths:
            with open(pdf_file, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for pg in reader.pages:
                    writer.add_page(pg)

        with open(merged_path, "wb") as out_f:
            writer.write(out_f)

        print(f"Created merged PDF => {merged_name}")
    else:
        print("\nNot merging or no PDFs to merge.")

    print("\nDone!\n")


if __name__ == "__main__":
    main()
