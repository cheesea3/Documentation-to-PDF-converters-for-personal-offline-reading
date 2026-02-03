#!/usr/bin/env python3
"""
Scrape Ruby on Rails 8.0 Guides from https://guides.rubyonrails.org/ and export them to PDF.

Requires:
  pip install playwright PyPDF2
  playwright install

Usage:
  python rails_8_guides_to_pdf.py
"""

import re
import time
import os
from pathlib import Path

import PyPDF2
from playwright.sync_api import sync_playwright, TimeoutError

# ---------------------------
# Configuration
# ---------------------------

GUIDES_BASE_URL = "https://guides.rubyonrails.org/"  # We'll treat this as the host for the 8.0 guides
OUTPUT_DIR = "rails_8_guides"

# A set of known guide paths we want to capture – derived from the official index links:
RAILS_8_GUIDE_PAGES = [
    # Start Here
    "getting_started.html",
    "install_ruby_on_rails.html",

    # Models
    "active_record_basics.html",
    "active_record_migrations.html",
    "active_record_validations.html",
    "active_record_callbacks.html",
    "association_basics.html",
    "active_record_querying.html",
    "active_model_basics.html",

    # Views
    "action_view_overview.html",
    "layouts_and_rendering.html",
    "action_view_helpers.html",
    "form_helpers.html",

    # Controllers
    "action_controller_overview.html",
    "action_controller_advanced_topics.html",
    "routing.html",

    # Other Components
    "active_support_core_extensions.html",
    "action_mailer_basics.html",
    "action_mailbox_basics.html",
    "action_text_overview.html",
    "active_job_basics.html",
    "active_storage_overview.html",
    "action_cable_overview.html",

    # Digging Deeper
    "i18n.html",
    "testing.html",
    "debugging_rails_applications.html",
    "configuring.html",
    "command_line.html",
    "asset_pipeline.html",
    "working_with_javascript_in_rails.html",
    "autoloading_and_reloading_constants.html",
    "api_app.html",

    # Going to Production
    "tuning_performance_for_deployment.html",
    "caching_with_rails.html",
    "security.html",
    "error_reporting.html",

    # Advanced Active Record
    "active_record_multiple_databases.html",
    "active_record_composite_primary_keys.html",

    # Extending Rails
    "rails_on_rack.html",
    "generators.html",

    # Contributing
    "contributing_to_ruby_on_rails.html",
    "api_documentation_guidelines.html",
    "ruby_on_rails_guides_guidelines.html",
    "development_dependencies_install.html",

    # Policies
    "maintenance_policy.html",

    # Release Notes
    "upgrading_ruby_on_rails.html",
    "8_0_release_notes.html",
    "7_2_release_notes.html",
    "7_1_release_notes.html",
    "7_0_release_notes.html",
    "6_1_release_notes.html",
    "6_0_release_notes.html",
    "5_2_release_notes.html",
    "5_1_release_notes.html",
    "5_0_release_notes.html",
    "4_2_release_notes.html",
    "4_1_release_notes.html",
    "4_0_release_notes.html",
    "3_2_release_notes.html",
    "3_1_release_notes.html",
    "3_0_release_notes.html",
    "2_3_release_notes.html",
    "2_2_release_notes.html",
]

# Whether to also PDF-ify the main index page "index.html"
INCLUDE_MAIN_INDEX = True

# If True, merges all the PDFs at the end into one large "rails_8_guides_merged.pdf"
MERGE_ALL = True

# Timeout for each navigation
NAV_TIMEOUT_MS = 30000  # 30 seconds

# List of selectors we want to remove from final PDF layout
# We'll remove the large site header, top nav, mobile nav, footers, etc.
REMOVE_SELECTORS = [
    "#mobile-navigation-bar",
    "#page-header",
    "header",
    "#complementary",        # very bottom license + trademark text
    "footer",                # any <footer> tag
    "script", "noscript",    # scripts
    ".back-to-top",          # little "Back to top" link
    "#more-info-links",      # "More Ruby on Rails" dropdown
    "#more-info",            # button for it
    "#mobile-navigation-bar",# mobile nav bar
    "#feature-nav",          # top left nav
    "#feature",
    ".guides-index",         # the big guides index on each page
]

# Some custom CSS to remove leftover gaps or style code blocks, etc.
CUSTOM_CSS = r"""
body {
  font-family: "Arial", sans-serif;
  line-height: 1.4;
  font-size: 15px;
  margin: 0 auto;
  padding: 0 2em;
  max-width: 900px;
  color: #000;
}

/* Hide leftover wrappers or any undesired blocks if still present */
#guides,
nav.guides-index-large,
nav.guides-index-small,
nav#column-side,
#mobile-navigation-bar {
  display: none !important;
  visibility: hidden !important;
  margin: 0 !important;
  padding: 0 !important;
}

/* Style code blocks */
pre, code, .highlight {
  background: #f5f5f5;
  border: 1px solid #ccc;
  display: block;
  padding: 0.75em;
  border-radius: 4px;
  overflow-x: auto;
  margin-bottom: 1em;
}
"""

# ---------------------------
# Implementation
# ---------------------------

def create_out_dir():
    out_path = Path(OUTPUT_DIR)
    out_path.mkdir(parents=True, exist_ok=True)
    return out_path

def sanitize_filename(fname: str) -> str:
    # simple approach: remove anything not allowed in typical filenames
    return re.sub(r'[\\/:*?"<>|]', '', fname)

def remove_unwanted(page):
    """Remove unwanted DOM elements by the config SELECTORS list."""
    for sel in REMOVE_SELECTORS:
        page.evaluate(f'''
          () => {{
            const badNodes = document.querySelectorAll("{sel}");
            badNodes.forEach(n => n.remove());
          }}
        ''')

def fetch_page(page, url):
    """Goto the given URL with retries for potential timeouts."""
    try:
        page.goto(url, wait_until="networkidle", timeout=NAV_TIMEOUT_MS)
        time.sleep(1)  # small pause to let dynamic JS settle
        return True
    except TimeoutError:
        print(f"Timeout visiting: {url}")
        return False

def main():
    out_dir = create_out_dir()

    pdf_files = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # 1) Optionally process the "index.html" main Rails 8.0 page
        if INCLUDE_MAIN_INDEX:
            index_url = GUIDES_BASE_URL + "index.html"
            print(f"Processing main index => {index_url}")
            success = fetch_page(page, index_url)
            if success:
                remove_unwanted(page)
                page.add_style_tag(content=CUSTOM_CSS)
                # create PDF name
                index_pdf_name = sanitize_filename("01-Rails8Index") + ".pdf"
                index_path = out_dir / index_pdf_name

                page.pdf(
                    path=str(index_path),
                    format="A4",
                    margin={
                        "top": "15mm",
                        "bottom": "15mm",
                        "left": "15mm",
                        "right": "15mm",
                    },
                    print_background=True
                )
                pdf_files.append(str(index_path))

        # 2) For each known guide page
        guide_idx = 2 if INCLUDE_MAIN_INDEX else 1
        for guide_page in RAILS_8_GUIDE_PAGES:
            url = GUIDES_BASE_URL + guide_page
            print(f"[{guide_idx}] => {url}")
            # Make a PDF name from the guide's file name
            base_title = guide_page.replace(".html", "")
            pdf_name = f"{str(guide_idx).zfill(2)}-{sanitize_filename(base_title)}.pdf"
            out_pdf = out_dir / pdf_name

            new_page = browser.new_page()
            success = fetch_page(new_page, url)
            if not success:
                new_page.close()
                continue

            remove_unwanted(new_page)
            new_page.add_style_tag(content=CUSTOM_CSS)

            new_page.pdf(
                path=str(out_pdf),
                format="A4",
                margin={
                    "top": "15mm",
                    "bottom": "15mm",
                    "left": "15mm",
                    "right": "15mm",
                },
                print_background=True
            )
            print(f"  => saved {pdf_name}")
            pdf_files.append(str(out_pdf))

            new_page.close()
            guide_idx += 1

        browser.close()

    # 3) Optionally merge all PDFs
    if MERGE_ALL and pdf_files:
        merged_name = out_dir / "rails_8_guides_merged.pdf"
        print(f"\nMerging {len(pdf_files)} PDFs into => {merged_name}")
        writer = PyPDF2.PdfWriter()

        for pdf_path in pdf_files:
            try:
                with open(pdf_path, "rb") as pf:
                    reader = PyPDF2.PdfReader(pf)
                    for page_i in range(len(reader.pages)):
                        writer.add_page(reader.pages[page_i])
            except Exception as e:
                print(f"Warning: skipping {pdf_path} due to read error => {e}")

        with open(merged_name, "wb") as outf:
            writer.write(outf)
        print(f"Created merged PDF => {merged_name.name}")

    print("\nDone!")

if __name__ == "__main__":
    main()
