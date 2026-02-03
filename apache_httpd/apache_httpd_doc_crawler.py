#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apache_httpd_doc_crawler.py

Crawls https://httpd.apache.org/docs/current/ (English docs only),
skips other translations or repeated loops, and converts to PDF with pdfkit.
Merges them into a single PDF if desired.

Requires:
   - pip install requests beautifulsoup4 pdfkit PyPDF2
   - wkhtmltopdf installed (version 0.12.6 or similar)
"""

import os
import re
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import pdfkit
from PyPDF2 import PdfMerger

# -----------------------------
# CONFIG
# -----------------------------
START_URL = "https://httpd.apache.org/docs/current/"
DOMAIN = "httpd.apache.org"
OUTPUT_DIR = "apache_httpd_docs_pdf"
CRAWL_LIMIT = 200  # Safety cutoff

CREATE_SINGLE_PDF = True
MERGED_PDF_NAME = "Apache_HTTP_Server_24_Docs_Merged.pdf"

# Exclude other languages or unwanted docs:
EXCLUDE_KEYWORDS = [
    "zh-cn", "ja", "ko", "fr", "ru", "pt-br",  # translations
    "faq", "glossary", "license", "sitemap",  # other pages to skip
]

# Must match /docs/current/ in the path
DOC_PATH_REGEX = re.compile(r"^/docs/current/", re.IGNORECASE)

# If the path after /docs/current/ is a two-letter or five-letter locale code
# (like 'tr' or 'zh-cn'), skip it. We'll define a quick check for that:
LOCALE_CODE_REGEX = re.compile(r"^[a-z]{2}(\-[a-z]{2})?$", re.IGNORECASE)

# HTML elements to remove before generating PDF
SELECTORS_TO_REMOVE = [
    "header", "footer", "nav", "aside",
    "#page-header", "#footer",
    ".toplang", ".bottomlang", ".menu",
    "#comments_section", "#comments_thread",
    "script", "style", "form",
]

# Keep track of visited URLs to avoid loops
visited = set()
to_visit = [START_URL]
pdf_files = []

os.makedirs(OUTPUT_DIR, exist_ok=True)

# PDFKit config - remove the unsupported `--ignore-certificate-errors`:
pdfkit_config = pdfkit.configuration()
pdfkit_options = {
    # You can add other wkhtmltopdf flags here if needed, e.g.
    # "--enable-local-file-access": "",
    # "--disable-smart-shrinking": "",
}

def is_valid_link(href: str) -> bool:
    """Return True if href is a doc page in English under /docs/current/."""
    if not href:
        return False

    parsed = urlparse(href)
    if parsed.netloc and parsed.netloc.lower() != DOMAIN:
        return False

    # Must match /docs/current/
    if not DOC_PATH_REGEX.search(parsed.path):
        return False

    # Skip if path has excluded keywords
    lower_path = parsed.path.lower()
    for kw in EXCLUDE_KEYWORDS:
        if kw in lower_path:
            return False

    # Check if splitted[2] is a locale code
    splitted = parsed.path.strip("/").split("/")
    if len(splitted) >= 3:
        # e.g. /docs/current/tr/something => splitted[2] = 'tr'
        if LOCALE_CODE_REGEX.match(splitted[2]):
            return False

    return True

def fetch_and_cleanup_html(url: str) -> str:
    """Fetch HTML from url, remove clutter, and return minimal content as string."""
    print(f"   -> GET {url}")
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # Remove extraneous elements
    for sel in SELECTORS_TO_REMOVE:
        for tag in soup.select(sel):
            tag.decompose()

    # Attempt to isolate #page-content
    content_div = soup.find("div", id="page-content")
    if content_div:
        return str(content_div)
    else:
        return str(soup.body or soup)

def html_to_pdf(html_str: str, pdf_path: str):
    """Convert the HTML content to PDF using pdfkit."""
    try:
        pdfkit.from_string(
            html_str,
            pdf_path,
            configuration=pdfkit_config,
            options=pdfkit_options
        )
    except Exception as e:
        print(f"      [!] pdfkit error on {pdf_path}: {e}")

def merge_pdfs(pdf_list: list, output_pdf: str):
    """Merge multiple PDFs into one using PyPDF2."""
    merger = PdfMerger()
    for pdf_file in pdf_list:
        try:
            merger.append(pdf_file)
        except Exception as e:
            print(f"      [!] Error merging {pdf_file}: {e}")
    merger.write(output_pdf)
    merger.close()

def main():
    page_count = 0

    while to_visit and len(visited) < CRAWL_LIMIT:
        url = to_visit.pop()
        if url in visited:
            continue
        visited.add(url)

        print(f"[Crawl] {url}")
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
        except Exception as e:
            print(f"   !! Error fetching {url}: {e}")
            continue

        # Extract new links
        soup = BeautifulSoup(resp.text, "html.parser")
        for a_tag in soup.find_all("a", href=True):
            link_url = urljoin(url, a_tag["href"])
            if link_url not in visited and is_valid_link(link_url):
                to_visit.append(link_url)

        # Convert this page to PDF
        parsed = urlparse(url)
        path_part = parsed.path.strip("/")
        if not path_part:
            path_part = "index"
        pdf_filename = path_part.replace("/", "-") + ".pdf"
        pdf_fullpath = os.path.join(OUTPUT_DIR, pdf_filename)

        try:
            cleaned_html = fetch_and_cleanup_html(url)
            html_to_pdf(cleaned_html, pdf_fullpath)
            pdf_files.append(pdf_fullpath)
            page_count += 1
        except Exception as e:
            print(f"   !! Error converting {url} -> {pdf_fullpath}: {e}")

    print(f"\n[*] Visited {len(visited)} pages. Created {page_count} PDFs in {OUTPUT_DIR}.")

    if CREATE_SINGLE_PDF and pdf_files:
        merged_pdf_path = os.path.join(OUTPUT_DIR, MERGED_PDF_NAME)
        print(f"[*] Merging {len(pdf_files)} PDFs -> {merged_pdf_path}")
        merge_pdfs(pdf_files, merged_pdf_path)
        print("[*] Merge complete.")

if __name__ == "__main__":
    main()
Cl