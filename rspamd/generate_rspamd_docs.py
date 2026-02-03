#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rspamd_doc_crawler_improved.py

Crawl https://rspamd.com/doc/ and produce PDFs of each doc page.
- Fixes weird encoding via ftfy
- Rewrites doc links from .html -> .pdf
- Optionally merges them all into a single PDF

Requires:
   pip install requests beautifulsoup4 pdfkit PyPDF2 ftfy
   wkhtmltopdf installed
"""

import os
import re
import requests
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
import pdfkit
from PyPDF2 import PdfMerger
import ftfy  # for fixing weird apostrophes

START_URL = "https://rspamd.com/doc/"
DOMAIN = "rspamd.com"
OUTPUT_DIR = "rspamd_docs_pdf"
CRAWL_LIMIT = 200

CREATE_SINGLE_PDF = True
MERGED_PDF_NAME = "Rspamd_Docs_Merged.pdf"

EXCLUDE_KEYWORDS = [
    # e.g. "ru", "faq", ...
]

DOC_PATH_REGEX = re.compile(r"^/doc/", re.IGNORECASE)

SELECTORS_TO_REMOVE = [
    "header", "footer", "nav", "aside",
    "#page-header", "#footer",
    ".toplang", ".bottomlang", ".menu",
    "#comments_section", "#comments_thread",
    "script", "style", "form",
]

visited = set()
to_visit = [START_URL]
pdf_files = []

os.makedirs(OUTPUT_DIR, exist_ok=True)

pdfkit_config = pdfkit.configuration()
pdfkit_options = {
    # You can add or remove pdfkit wkhtmltopdf options here
    # e.g. "--enable-local-file-access": "",
}

def should_exclude(path_str: str) -> bool:
    lower_path = path_str.lower()
    for kw in EXCLUDE_KEYWORDS:
        if kw in lower_path:
            return True
    return False

def is_valid_link(href: str) -> bool:
    if not href:
        return False
    parsed = urlparse(href)
    if parsed.netloc and parsed.netloc.lower() != DOMAIN:
        return False
    if not DOC_PATH_REGEX.search(parsed.path):
        return False
    if should_exclude(parsed.path):
        return False
    return True

def rewrite_links(soup, base_url):
    """Change /doc/foo.html -> doc-foo.html.pdf to reference local PDF"""
    for a_tag in soup.find_all("a", href=True):
        link_url = urljoin(base_url, a_tag["href"])
        if is_valid_link(link_url):
            parsed = urlparse(link_url)
            # replace .html with .pdf naming
            path_part = parsed.path.strip("/")
            if not path_part:
                path_part = "index"
            pdf_filename = path_part.replace("/", "-").replace(".html", "") + ".pdf"
            a_tag["href"] = pdf_filename  # now it points to the PDF
        else:
            # external or excluded link, do nothing or remove
            pass

def fetch_and_cleanup_html(url: str) -> str:
    print(f"   -> GET {url}")
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    # Fix weird encoding
    html = ftfy.fix_text(resp.text, uncurl_quotes=True)
    soup = BeautifulSoup(html, "html.parser")
    # Remove clutter
    for sel in SELECTORS_TO_REMOVE:
        for tag in soup.select(sel):
            tag.decompose()
    # Rewrite doc links to .pdf
    rewrite_links(soup, url)
    # Grab main content
    content_div = soup.select_one(".r-docs-content")
    if content_div:
        return str(content_div)
    else:
        return str(soup.body or soup)

def html_to_pdf(html_str: str, pdf_path: str):
    try:
        pdfkit.from_string(html_str, pdf_path,
                           configuration=pdfkit_config,
                           options=pdfkit_options)
    except Exception as e:
        print(f"[!] pdfkit error on {pdf_path}: {e}")

def merge_pdfs(pdf_list: list, output_pdf: str):
    merger = PdfMerger()
    for pdf_file in pdf_list:
        try:
            merger.append(pdf_file)
        except Exception as e:
            print(f"[!] Error merging {pdf_file}: {e}")
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
        soup = BeautifulSoup(resp.text, "html.parser")
        for a_tag in soup.find_all("a", href=True):
            link_url = urljoin(url, a_tag["href"])
            if link_url not in visited and is_valid_link(link_url):
                to_visit.append(link_url)
        parsed = urlparse(url)
        path_part = parsed.path.strip("/")
        if not path_part:
            path_part = "index"
        pdf_filename = path_part.replace("/", "-") + ".pdf"
        pdf_path = os.path.join(OUTPUT_DIR, pdf_filename)
        try:
            # Actually fetch the content again, with cleaning
            cleaned_html = fetch_and_cleanup_html(url)
            html_to_pdf(cleaned_html, pdf_path)
            pdf_files.append(pdf_path)
            page_count += 1
        except Exception as e:
            print(f"   !! Error converting {url} -> {pdf_path}: {e}")
            continue
    print(f"\n[*] Visited {len(visited)} pages, created {page_count} PDFs in {OUTPUT_DIR}")
    if CREATE_SINGLE_PDF and pdf_files:
        merged_pdf_path = os.path.join(OUTPUT_DIR, MERGED_PDF_NAME)
        print(f"[*] Merging {len(pdf_files)} PDFs -> {merged_pdf_path}")
        merge_pdfs(pdf_files, merged_pdf_path)
        print("[*] Merge complete.")

if __name__ == "__main__":
    main()
