#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Combine multiple Certbot documentation pages from Read the Docs into a single
HTML file, then render as PDF. Attempts to produce a cleaner, more readable PDF.
"""

import os
import time
import logging
import requests
import pdfkit
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

################################################################################
# CONFIG
################################################################################

# Path to your wkhtmltopdf binary.
# Adjust this to wherever wkhtmltopdf is installed on your system:
WKHTMLTOPDF_PATH = "/usr/local/bin/wkhtmltopdf"

# Options for pdfkit / wkhtmltopdf. Tweak as needed for best results.
PDFKIT_OPTIONS = {
    # "enable-local-file-access": None,  # If referencing local CSS/images, uncomment
    # "ssl-protocol": "TLSv1.2",         # Possibly needed for older wkhtmltopdf or debugging
}

# Output filenames for the combined HTML and final PDF
OUTPUT_HTML_FILENAME = "certbot_docs_combined.html"
OUTPUT_PDF_FILENAME = "certbot_docs_merged.pdf"

# Base URL for the Certbot stable documentation
BASE_URL = "https://eff-certbot.readthedocs.io/en/stable/"

# The specific pages (in order) you want to combine:
URLS_IN_ORDER = [
    "index.html",       # Landing page
    "intro.html",       # Introduction
    "what.html",        # What is a Certificate?
    "install.html",     # Get Certbot
    "using.html",       # User Guide
    "contributing.html",# Developer Guide
    "packaging.html",   # Packaging Guide
    "compatibility.html",# Backwards Compatibility
    "resources.html",   # Resources
    "api.html",         # API Documentation
]

################################################################################
# LOGGING
################################################################################

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

################################################################################
# HELPER FUNCTION: fetch_and_clean
################################################################################

def fetch_and_clean(relative_path: str) -> (str, str):
    """
    1) Download the doc from BASE_URL + relative_path.
    2) Use BeautifulSoup to remove sidebars, navigation, and other extraneous
       elements typical of the ReadTheDocs theme.
    3) Return (doc_html, doc_title) => the cleaned HTML + a best-guess doc title.
    """
    full_url = urljoin(BASE_URL, relative_path)
    logging.info(f"Fetching: {full_url}")

    try:
        resp = requests.get(full_url, timeout=30)
        resp.raise_for_status()
    except Exception as exc:
        logging.error(f"!! Error fetching {full_url}: {exc}")
        return ("", "")

    soup = BeautifulSoup(resp.text, "html.parser")

    # Try to grab a decent page title
    if soup.find("title"):
        doc_title = soup.find("title").get_text(strip=True)
    else:
        doc_title = relative_path  # fallback

    # Remove sidebars, footers, search bars, top nav, etc. (typical of RTD theme)
    for side_elm in soup.select("nav.wy-nav-side, div.wy-side-scroll, nav.wy-nav-top, div.wy-breadcrumbs"):
        side_elm.decompose()
    for foot_elm in soup.select("footer, form#rtd-search-form, div.wy-nav-content-wrap > nav"):
        foot_elm.decompose()

    # Attempt to isolate the main content. Usually it's <div role="main" class="document">
    main_content = soup.find("div", {"role": "main"})
    if not main_content:
        # fallback to entire body if needed
        main_content = soup.find("body") or soup

    main_html = str(main_content)
    return (main_html, doc_title)

################################################################################
# HELPER FUNCTION: rewrite_links_big_html
################################################################################

def rewrite_links_big_html(soup: BeautifulSoup, doc_id: str):
    """
    Within one doc, rename all anchor IDs to be unique to doc_id (e.g. 'doc-intro_anchor')
    so cross-page references won't clash. Also transform links like 'intro.html#anchor'
    into '#doc-intro_anchor'. Internal links that reference the same doc (#anchor) become
    '#doc-{doc_id}_anchor'.
    """
    # 1) Add doc_id prefix to all existing anchor IDs
    for anchor_elm in soup.select('[id]'):
        old_id = anchor_elm["id"]
        new_id = f"doc-{doc_id}_{old_id}"
        anchor_elm["id"] = new_id

    # Also rename name= attributes (rare in newer HTML, but might exist)
    for anchor_elm in soup.select('[name]'):
        old_name = anchor_elm["name"]
        new_name = f"doc-{doc_id}_{old_name}"
        anchor_elm["name"] = new_name

    # 2) Rewrite <a href="..."> references to maintain cross-page anchors
    for a_tag in soup.find_all("a", href=True):
        href_val = a_tag["href"]
        parsed = urlparse(href_val)

        # If the link is a local reference (no scheme, netloc)
        if not parsed.scheme and not parsed.netloc:
            # e.g. "intro.html#section" or "#section"
            if ".html" in href_val.lower():
                # Something like "intro.html#anchor"
                parts = href_val.split("#", 1)
                if len(parts) == 2:
                    page_part, anchor_part = parts
                    page_part = page_part.lower().replace(".html", "")
                    new_href = f"#doc-{page_part}_{anchor_part}"
                else:
                    # e.g. "intro.html" with no #anchor
                    page_part = href_val.lower().replace(".html", "")
                    new_href = f"#doc-{page_part}_"
                a_tag["href"] = new_href
            elif href_val.startswith("#"):
                # link to anchor in the *same doc*
                anchor_only = href_val[1:]
                new_href = f"#doc-{doc_id}_{anchor_only}"
                a_tag["href"] = new_href
        # Otherwise external links are left alone.

################################################################################
# MAIN
################################################################################

def main():
    # Step 1: Download and parse each doc in URLS_IN_ORDER
    combined_docs = []
    for page in URLS_IN_ORDER:
        doc_id = page.lower().replace(".html", "")
        doc_html, doc_title = fetch_and_clean(page)
        if doc_html:
            combined_docs.append((doc_id, doc_title, doc_html))
        time.sleep(1)  # be polite

    # Step 2: Create a fresh HTML skeleton
    big_soup = BeautifulSoup(
        "<html><head><meta charset='utf-8'/><title>Certbot Docs Combined</title>"
        "</head><body></body></html>", "html.parser"
    )
    body_tag = big_soup.find("body")

    # Step 3: Insert each doc into the combined HTML, rewriting anchors
    for doc_id, doc_title, doc_html in combined_docs:
        doc_soup = BeautifulSoup(doc_html, "html.parser")
        rewrite_links_big_html(doc_soup, doc_id)

        # Insert an H1 to mark the start of each doc
        h1 = big_soup.new_tag("h1", id=f"doc-heading-{doc_id}")
        h1.string = doc_title
        body_tag.append(h1)

        # Now append the (cleaned & link-rewritten) doc content
        for child in doc_soup.contents:
            body_tag.append(child)

        # Insert an HR after each doc
        hr_tag = big_soup.new_tag("hr")
        body_tag.append(hr_tag)

    # Step 4: Write the combined HTML out to disk
    final_html_str = str(big_soup)
    with open(OUTPUT_HTML_FILENAME, "w", encoding="utf-8") as f:
        f.write(final_html_str)
    logging.info(f"Wrote combined HTML to {OUTPUT_HTML_FILENAME}")

    # Step 5: Convert the big HTML to a single PDF via pdfkit + wkhtmltopdf
    try:
        pdfkit.from_file(
            OUTPUT_HTML_FILENAME,
            OUTPUT_PDF_FILENAME,
            configuration=pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH),
            options=PDFKIT_OPTIONS
        )
        logging.info(f"Successfully created PDF => {OUTPUT_PDF_FILENAME}")
    except Exception as ex:
        logging.error(f"pdfkit error: {ex}")

if __name__ == "__main__":
    main()
