#!/usr/bin/env python3
"""
Scrape Debian 12 tutorials from server-world.info, remove extraneous elements,
convert each page to PDF, and merge them into one big PDF.

Requires:
  pip install playwright PyPDF2
  playwright install

Usage:
  python server_world_debian12_hybrid.py

Author: ChatGPT
"""

import sys
import re
import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import PyPDF2

# -------------------------------
# Configuration
# -------------------------------

MAIN_URL = "https://www.server-world.info/en/note?os=Debian_12&p=download"

# If True, merge all created PDFs into one mega PDF at the end
MERGE_PDFS = True

# Directory where we’ll store PDFs
OUTPUT_DIR = "serverworld_debian12_final"

# Time to wait (ms) for .goto() calls
GOTO_TIMEOUT_MS = 60_000  # 60 seconds

# How many times to retry if a page times out
MAX_RETRIES = 2

# On the *main* Debian 12 index page, we want to keep the left nav (#left)
# so we only remove these:
REMOVE_ON_INDEX = [
    "header.header_wrap",
    "div#top-menu",
    "div#footer",
    "div#bann",      # ads banner
    "#right",
    "ins.adsbygoogle",
    "iframe",
    "script",
]

# On *subpages*, we remove everything above plus #left:
REMOVE_ON_SUBPAGE = REMOVE_ON_INDEX + ["#left"]

# Basic custom CSS to hide leftover bits, style code blocks, etc.
CUSTOM_CSS = r"""
/* Hide top/bottom clutter if it exists */
#top-menu, #footer, #bann, #right {
    display: none !important;
}
body {
    font-family: "Arial", sans-serif;
    line-height: 1.4;
    font-size: 15px;
    color: #000;
    margin: 0 auto;
    padding: 0 1em;
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
pre, code, .cmd, .cmdtxt, .term {
    font-family: "Courier New", Consolas, monospace !important;
    background-color: #f5f5f5;
    border: 1px solid #aaa;
    padding: 0.8em;
    border-radius: 4px;
    display: block;
    color: #333;
    overflow-x: auto;
    margin: 1em 0;
}
"""

# -------------------------------
# Helpers
# -------------------------------

def create_output_dir() -> Path:
    """Create the output directory if needed; return Path object."""
    out_path = Path(OUTPUT_DIR)
    out_path.mkdir(exist_ok=True, parents=True)
    return out_path

def remove_extras(page, selectors):
    """Remove from the DOM the given CSS selectors."""
    for sel in selectors:
        page.evaluate(
            f"""
            () => {{
                const elements = document.querySelectorAll("{sel}");
                elements.forEach(el => el.remove());
            }}
            """
        )

def sanitize_filename(fname: str) -> str:
    """Remove characters that could break filenames."""
    return re.sub(r'[\\/:*?"<>|]', '', fname)

def parse_numbered_title(link_text: str) -> (str, str):
    """
    If link_text starts with e.g. '(02) Some Title', return ("02", "Some Title").
    Otherwise return ("", original_text).
    """
    # e.g. (07) => group(1)="07", remainder => group(2)="something"
    match = re.match(r'^\((\d+)\)\s*(.*)$', link_text.strip())
    if match:
        return match.group(1), match.group(2).strip()
    else:
        return "", link_text.strip()

def make_pdf_filename(global_idx: int, link_text: str) -> str:
    """
    Create a PDF filename. If link_text has a leading (NN),
    use that for the numeric prefix. Otherwise fallback to `global_idx`.
    Example: link_text="(05) Configure APT" => "05-Configure APT.pdf"
    If no leading number => "02-Some Title.pdf"
    """
    num_str, remainder = parse_numbered_title(link_text)
    if num_str:
        # e.g. "05" + "Configure APT"
        fname = f"{num_str}-{remainder}"
    else:
        # fallback "02-Some Title"
        fname = f"{str(global_idx).zfill(2)}-{link_text}"
    # sanitize
    fname = sanitize_filename(fname)
    # truncate if super long
    if len(fname) > 100:
        fname = fname[:100] + "..."
    return f"{fname}.pdf"

def fetch_page(new_page, url) -> bool:
    """
    Attempt to goto `url`, retry up to MAX_RETRIES times if timed out.
    Return True if success, False if skipping after repeated timeouts.
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            new_page.goto(url, wait_until="networkidle", timeout=GOTO_TIMEOUT_MS)
            time.sleep(1)
            return True
        except PlaywrightTimeout:
            print(f"  => Timeout visiting {url}, attempt {attempt}/{MAX_RETRIES}")
            if attempt >= MAX_RETRIES:
                print(f"  => Skipping {url}")
                return False
    return False

def gather_left_nav_links(page):
    """
    On the main index page, gather Debian_12 links from #left .navi a
    Return list of (url, link_text).
    """
    # JavaScript code to convert relative to absolute:
    # `page.evaluate('new URL("someRelative", document.location).href')`
    link_els = page.query_selector_all("#left .navi a[href*='Debian_12']")
    items = []
    seen = set()
    for el in link_els:
        href = el.get_attribute("href") or ""
        text = (el.inner_text() or "").strip()
        if not href or "javascript:" in href:
            continue
        # Convert to absolute in Python land:
        #   or do a short JS snippet: abs_url = page.evaluate('new URL(href, document.location).href')
        abs_url = page.evaluate(f'new URL("{href}", window.location.href).href')
        if abs_url not in seen:
            seen.add(abs_url)
            items.append((abs_url, text))
    return items


# -------------------------------
# Main script
# -------------------------------
def main():
    out_dir = create_output_dir()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # 1) Visit main Debian12 index page
        print(f"Visiting main index => {MAIN_URL}")
        try:
            page.goto(MAIN_URL, wait_until="networkidle", timeout=GOTO_TIMEOUT_MS)
        except PlaywrightTimeout:
            print("Main page timed out. Exiting early.")
            return
        time.sleep(2)

        # 2) Remove extraneous elements from index page, but keep #left
        remove_extras(page, REMOVE_ON_INDEX)
        page.add_style_tag(content=CUSTOM_CSS)

        # 3) Gather all links from the left nav
        nav_links = gather_left_nav_links(page)
        print(f"Found {len(nav_links)} Debian_12 links in #left .navi.")

        # 4) Save the main index page’s PDF
        index_pdf_path = out_dir / "01-Debian12_index.pdf"
        page.pdf(
            path=str(index_pdf_path),
            format="A4",
            print_background=True,
            margin={"top": "15mm", "bottom": "15mm", "left": "10mm", "right": "10mm"}
        )
        print(f"Saved index PDF => {index_pdf_path.name}")

        all_pdfs = [str(index_pdf_path)]  # We’ll merge them at the end

        # 5) For each sub link => open, remove #left, PDF
        link_counter = 2
        for (url, link_text) in nav_links:
            # Open in a fresh tab
            subpage = browser.new_page()
            print(f"\n[{link_counter}/{len(nav_links)}] => {link_text} => {url}")

            if not fetch_page(subpage, url):
                subpage.close()
                continue  # skip if timed out fully

            remove_extras(subpage, REMOVE_ON_SUBPAGE)
            subpage.add_style_tag(content=CUSTOM_CSS)

            pdf_name = make_pdf_filename(link_counter, link_text)
            pdf_path = out_dir / pdf_name
            # Save
            subpage.pdf(
                path=str(pdf_path),
                format="A4",
                print_background=True,
                margin={"top": "15mm", "bottom": "15mm", "left": "10mm", "right": "10mm"}
            )
            print(f"  => PDF saved: {pdf_name}")

            all_pdfs.append(str(pdf_path))
            subpage.close()
            link_counter += 1

        # Done with the browser
        browser.close()

    # 6) Merge if desired
    if MERGE_PDFS and all_pdfs:
        final_name = "serverworld-debian12-merged.pdf"
        final_path = Path(out_dir) / final_name
        print(f"\nMerging {len(all_pdfs)} PDFs into => {final_path.name}")

        writer = PyPDF2.PdfWriter()
        for pdf_file in all_pdfs:
            try:
                with open(pdf_file, "rb") as f:
                    reader = PyPDF2.PdfReader(f)
                    for page_idx in range(len(reader.pages)):
                        writer.add_page(reader.pages[page_idx])
            except Exception as ex:
                print(f"  [WARN] Skipping {pdf_file} due to read error => {ex}")

        with open(final_path, "wb") as outf:
            writer.write(outf)
        print(f"Done! Created merged PDF => {final_path.name}")
    else:
        print("\nNo merging was done or no PDFs found.")

    print("\nAll done!\n")


if __name__ == "__main__":
    main()
