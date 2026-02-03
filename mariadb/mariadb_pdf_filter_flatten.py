#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mariadb_kb_crawler.py
Crawl https://mariadb.com/kb/en/documentation/ and produce PDFs of each doc page.
Optionally merges them into a single PDF at the end.
"""

import os
import re
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import pdfkit

# Optional: For merging PDFs
from PyPDF2 import PdfMerger

# ------------------------------
# CONFIGURATION
# ------------------------------
START_URL = "https://mariadb.com/kb/en/documentation/"
DOMAIN = "mariadb.com"
OUTPUT_DIR = "mariadb_kb_docs_pdf"
CRAWL_LIMIT = 200  # Safety limit for # of pages

CREATE_SINGLE_PDF = True  # Merge all into one PDF at the end?
MERGED_PDF_NAME = "AllInOne_MariaDB_KB.pdf"

# We only want /kb/en/... paths for the docs. 
# Example: /kb/en/documentation/, /kb/en/sql-statements/, etc.
DOC_PATH_REGEX = re.compile(r"^/kb/en/[a-z0-9\-\_]+", re.IGNORECASE)

# Filenames that contain these terms will be excluded:
EXCLUDE_KEYWORDS = [
    "pricing",
    "services",
    "contact",
    "about-us",
    "download",
    "maxscale",
    "enterprise",
    "xpand",
    "skysql",
    "columnstore",
    # Add more if you wish to skip certain docs
]

# ------------------------------
# GLOBALS
# ------------------------------
visited = set()
to_visit = [START_URL]
pdf_files = []

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ------------------------------
# HELPER FUNCTIONS
# ------------------------------
def should_exclude_by_filename(filename: str) -> bool:
    """Return True if `filename` contains any unwanted keyword from EXCLUDE_KEYWORDS."""
    fn_lower = filename.lower()
    for kw in EXCLUDE_KEYWORDS:
        if kw in fn_lower:
            return True
    return False

def is_valid_link(href: str) -> bool:
    """
    Decide if the link is valid:
      - belongs to same domain (mariadb.com)
      - path starts with /kb/en/
      - exclude if the path or final PDF name triggers any of our EXCLUDE_KEYWORDS
    """
    if not href:
        return False
    
    parsed = urlparse(href)
    
    # Must be same domain
    if parsed.netloc and parsed.netloc != DOMAIN:
        return False
    
    # Must match /kb/en/ path
    if not DOC_PATH_REGEX.search(parsed.path):
        return False
    
    # Check exclude keywords (like 'pricing' or 'services')
    # We'll check them in the path
    lower_path = parsed.path.lower()
    for kw in EXCLUDE_KEYWORDS:
        if kw in lower_path:
            return False
    
    return True

def fetch_and_cleanup_html(url: str) -> str:
    """
    GET the HTML from `url`, remove typical nav/footers, etc. Return cleaned HTML as a string.
    """
    print(f"    -> GET {url}")
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    
    # Remove top nav, sidebars, footers, advertisement sections, forms, or anything else cluttering
    # This is somewhat guessy. We'll remove "header", "footer", any <aside>, any top nav, etc.
    for selector in [
        "nav", "header", "footer", "aside",
        "#top-nav", ".navbar", ".header", ".footer",
        ".nav-top-mobile", ".violator-wrap", "#menu-mobile", "#breadcrumbs",
        ".actions", ".box.node_info", ".well.node_info",
        ".sidebar", ".sidebar-first", ".sidebar-second",
        "#category_menu", ".modal", "#comments", ".page-footer", "#top_violator",
        "#footer", ".footer", "script", "style", "form", 
    ]:
        for tag in soup.select(selector):
            tag.decompose()
    
    # Possibly keep just the main content area. If there's a #content or .node or something:
    # But if uncertain, return the <body> entire or what's left
    content = soup.find("div", id="main")  # or #content, or "section"
    if not content:
        content = soup.body or soup
    
    cleaned_html = str(content)
    return cleaned_html

def html_to_pdf(html_str: str, pdf_path: str):
    """
    Convert raw HTML string to a PDF file using pdfkit.
    """
    # You can pass extra wkhtmltopdf options here if needed
    pdfkit.from_string(html_str, pdf_path)

def merge_pdfs(pdf_list: list, output_pdf: str):
    """Merge multiple PDFs into a single PDF using PyPDF2."""
    merger = PdfMerger()
    for pdf in pdf_list:
        merger.append(pdf)
    merger.write(output_pdf)
    merger.close()

# ------------------------------
# MAIN LOGIC
# ------------------------------
def main():
    while to_visit and len(visited) < CRAWL_LIMIT:
        url = to_visit.pop()
        if url in visited:
            continue
        visited.add(url)
        print(f"[Crawl] {url}")

        # Attempt to fetch
        try:
            page_resp = requests.get(url, timeout=15)
            page_resp.raise_for_status()
        except Exception as e:
            print(f"   !! Error fetching {url}: {e}")
            continue

        # Extract links
        soup = BeautifulSoup(page_resp.text, "html.parser")
        for a_tag in soup.find_all("a", href=True):
            link_url = urljoin(url, a_tag["href"])
            if is_valid_link(link_url) and link_url not in visited:
                to_visit.append(link_url)

        # Prepare a PDF filename from path
        parsed = urlparse(url)
        path_part = parsed.path.strip("/")
        if not path_part:
            path_part = "index"
        # Convert path slashes -> dashes
        path_part = path_part.replace("/", "-")

        # If final filename has any exclude keywords, skip
        if should_exclude_by_filename(path_part):
            print(f"   -> Skipping due to exclude keyword in filename: {path_part}")
            continue

        pdf_filename = path_part + ".pdf"
        pdf_filepath = os.path.join(OUTPUT_DIR, pdf_filename)

        # Fetch + clean the HTML, convert to PDF
        try:
            cleaned_html = fetch_and_cleanup_html(url)
            html_to_pdf(cleaned_html, pdf_filepath)
            pdf_files.append(pdf_filepath)
        except Exception as e:
            print(f"   !! Error converting {url} -> {pdf_filepath} : {e}")

    # Optionally merge all PDFs
    if CREATE_SINGLE_PDF and pdf_files:
        merged_path = os.path.join(OUTPUT_DIR, MERGED_PDF_NAME)
        print(f"[*] Merging {len(pdf_files)} PDFs into {merged_path}")
        merge_pdfs(pdf_files, merged_path)

    print("Done!")
    print(f"Visited {len(visited)} pages. Output in {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
