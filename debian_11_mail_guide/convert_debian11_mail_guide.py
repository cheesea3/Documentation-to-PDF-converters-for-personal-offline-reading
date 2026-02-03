#!/usr/bin/env python3
"""
Fetches the Debian Postfix tutorial series from LinuxBabe and converts each part into a PDF.
Also can merge all parts into a single PDF, if you like.

Dependencies:
  pip install playwright PyPDF2
  playwright install

Usage:
  python linuxbabe_debian_email_series_to_pdf.py
  Or specify custom output folder, etc.

Author: ChatGPT
"""

import sys
import re
import os
import time
from pathlib import Path

import PyPDF2
from playwright.sync_api import sync_playwright


# --------------------------------------------------
# Configuration
# --------------------------------------------------

# Main part-1 URL
MAIN_URL = "https://www.linuxbabe.com/mail-server/build-email-server-from-scratch-debian-postfix-smtp"

# Whether to merge all generated PDFs into one at the end
MERGE_PDFS = True

# PDF naming pattern
# We will generate something like:
#   "01-Set up a basic Postfix SMTP server.pdf"
#   "02-Set up Dovecot IMAP server and TLS encryption.pdf"
# etc.
# The final merged PDF is "linuxbabe-debian-email-tutorial-series.pdf"
OUTPUT_DIR = "linuxbabe-debian-email-series"  # folder to store PDFs

# CSS selectors to remove from each page
REMOVE_SELECTORS = [
    "header.header_wrap",      # top nav bar
    "#sidebar",                # side bar
    ".footer_wrap",            # footer area
    ".head_soc",               # social links on top
    ".widget_block",           # sidebar blocks
    "div.comment-respond",     # comment form
    "div.comments_template",   # entire comment section
    "script",                  # scripts
    "#wpadminbar",             # WP admin bar if present
    ".adsbygoogle",            # Google AdSense
    "ins.adsbygoogle",         # AdSense inline ads
    ".shareaholic-canvas",     # share related
    ".navigation",             # next/prev post navigation
]

# Extra CSS to hide leftover wrappers, enlarge content, etc.
CUSTOM_CSS = """
/* Hide leftover placeholders or extraneous wrappers */
.widget, aside, .head_inner, .footer_wrap { display: none !important; }

/* Make content as wide as possible */
.single_wrap {
    width: 100% !important;
    margin: 0 auto;
    padding: 0 1em;
}

/* Tweak fonts */
body {
    font-family: "Arial", sans-serif;
    line-height: 1.4;
    font-size: 15px;
    color: #000;
}

h1, h2, h3, h4 {
    margin-top: 1.25em;
}

p, ul, ol {
    margin-bottom: 1em;
}

/* Ensure images are fully visible in PDF */
img {
    max-width: 100% !important;
    height: auto !important;
}
"""


def create_output_dir():
    """Create output directory if it doesn't exist."""
    out_path = Path(OUTPUT_DIR)
    out_path.mkdir(exist_ok=True, parents=True)
    return out_path


def sanitize_filename(filename: str) -> str:
    """Remove characters that may cause problems in filenames."""
    # E.g. remove slashes, quotes, question marks, etc.
    return re.sub(r'[\\/:*?"<>|]', '', filename)


def remove_extraneous_elements(page):
    """Use the given remove selectors to get rid of unwanted elements."""
    for sel in REMOVE_SELECTORS:
        page.evaluate(
            f"""
            () => {{
                const badEls = document.querySelectorAll("{sel}");
                badEls.forEach(el => el.remove());
            }}
            """
        )


def make_pdf_filename(part_number: int, title_text: str) -> str:
    """Create a PDF filename like '02-Set up Dovecot IMAP server.pdf'."""
    # ensure part_number is at least two digits (01, 02, etc.)
    part_str = str(part_number).zfill(2)
    # limit how long the title can get
    title_text = title_text.strip()
    if len(title_text) > 60:
        title_text = title_text[:60] + "..."
    # sanitize
    title_text = sanitize_filename(title_text)
    return f"{part_str}-{title_text}.pdf"


def main():
    # Optional: parse command-line arguments if needed
    # For simplicity, we just proceed with the defaults.

    out_dir_path = create_output_dir()

    print(f"Creating PDFs in directory: {out_dir_path.resolve()}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # 1) Go to Part 1 (main URL).
        print(f"Fetching main Part 1 page: {MAIN_URL}")
        page.goto(MAIN_URL, wait_until="networkidle")
        time.sleep(1)

        # Remove extraneous elements
        remove_extraneous_elements(page)
        page.add_style_tag(content=CUSTOM_CSS)

        # Grab Part 1 title
        # We'll try to find the main h1
        part_1_title = page.title() or "Part1"
        # Sometimes the page title has " - LinuxBabe" or so
        # We can just remove " - LinuxBabe" etc.
        part_1_title = re.sub(r'\s*-\s*LinuxBabe.*$', '', part_1_title)

        # Save Part 1 PDF
        part_1_pdf = make_pdf_filename(1, part_1_title)
        part_1_pdf_path = out_dir_path / part_1_pdf
        page.pdf(
            path=str(part_1_pdf_path),
            format="A4",
            print_background=True,
            margin={"top": "15mm", "bottom": "15mm", "left": "10mm", "right": "10mm"}
        )
        print(f"Saved Part 1 PDF: {part_1_pdf}")

        # 2) Extract the 15 tutorial links (Parts 2-16).
        # They appear in an <ol> list. We'll locate them by standard CSS:
        # "ol li a" that have "https://www.linuxbabe.com/mail-server/..." in href, presumably.
        # Or just get them all from the <ol> block in the article body.
        tutorial_links = page.query_selector_all("ol li a")
        next_parts = []

        # We want only the tutorial links, so let's gather them along with anchor text.
        for link_el in tutorial_links:
            href = link_el.get_attribute("href")
            text = link_el.inner_text().strip()
            if href and href.startswith("https://www.linuxbabe.com/mail-server/"):
                next_parts.append((href, text))

        # Now let's fetch each next part, in order
        # part_number = 2 (since part1 is done)
        part_number = 2
        pdf_files = [str(part_1_pdf_path)]  # keep track for merging later
        for href, link_title in next_parts:
            print(f"\nFetching Part {part_number}: {link_title}")
            new_page = browser.new_page()
            new_page.goto(href, wait_until="networkidle")
            time.sleep(1)

            remove_extraneous_elements(new_page)
            new_page.add_style_tag(content=CUSTOM_CSS)

            # Make a short title from link_text or page title
            candidate_title = link_title
            if not candidate_title:
                # fallback to page.title()
                candidate_title = new_page.title()
            # remove trailing brand
            candidate_title = re.sub(r'\s*-\s*LinuxBabe.*$', '', candidate_title)

            # Save PDF
            pdf_name = make_pdf_filename(part_number, candidate_title)
            pdf_path = out_dir_path / pdf_name
            new_page.pdf(
                path=str(pdf_path),
                format="A4",
                print_background=True,
                margin={"top": "15mm", "bottom": "15mm", "left": "10mm", "right": "10mm"}
            )
            print(f"Saved Part {part_number} PDF => {pdf_path.name}")
            pdf_files.append(str(pdf_path))

            new_page.close()
            part_number += 1

        browser.close()

    # 3) (Optional) Merge all PDFs into one
    if MERGE_PDFS:
        merged_filename = "linuxbabe-debian-email-tutorial-series.pdf"
        merged_path = out_dir_path / merged_filename
        print(f"\nMerging {len(pdf_files)} PDFs into: {merged_path}")

        pdf_writer = PyPDF2.PdfWriter()
        for pdf_file in pdf_files:
            with open(pdf_file, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page_idx in range(len(reader.pages)):
                    pdf_writer.add_page(reader.pages[page_idx])

        with open(merged_path, "wb") as out_f:
            pdf_writer.write(out_f)

        print(f"Final merged PDF created at: {merged_filename}\n")
    else:
        print("\nNot merging PDFs (MERGE_PDFS=False). Done.\n")


if __name__ == "__main__":
    main()
