#!/usr/bin/env python3
"""
convert_fail2ban_wiki.py

1) Combines all *.md files in the current directory into one big markdown string.
2) Converts that to HTML (via python-markdown).
3) Converts that HTML to PDF (via pdfkit + wkhtmltopdf).
4) Saves "fail2ban_wiki.pdf".
"""

import glob
import markdown
import pdfkit

def main():
    # 1) Gather & combine .md files
    print("==> Combining *.md files into a single HTML string ...")
    md_files = sorted(glob.glob("*.md"))  # Sorted so the file order is predictable
    combined_markdown = ""

    for filename in md_files:
        with open(filename, "r", encoding="utf-8") as f:
            combined_markdown += f.read() + "\n\n"

    # 2) Convert that combined Markdown into HTML
    print("==> Converting combined Markdown into HTML with python-markdown ...")
    html_content = markdown.markdown(combined_markdown, extensions=['tables', 'fenced_code'])

    # Optionally wrap the HTML in a <head> and basic style
    # (pdfkit/wkhtmltopdf can handle raw HTML, but let's add a minimal structure)
    full_html = f"""
<html>
<head>
    <meta charset="utf-8">
    <title>Fail2Ban Wiki</title>
    <style>
      body {{
        font-family: sans-serif;
        margin: 1em;
      }}
      code, pre {{
        background: #f3f3f3;
        font-family: monospace;
      }}
    </style>
</head>
<body>
{html_content}
</body>
</html>
""".strip()

    # 3) Convert HTML -> PDF using pdfkit + wkhtmltopdf
    print("==> Generating PDF with pdfkit + wkhtmltopdf ...")
    pdfkit.from_string(full_html, "fail2ban_wiki.pdf", options={
        # Some example wkhtmltopdf options you might want:
        'enable-local-file-access': None,
        'quiet': None,
        # 'page-size': 'Letter',
        # 'margin-top': '0.75in',
        # 'margin-right': '0.75in',
        # 'margin-bottom': '0.75in',
        # 'margin-left': '0.75in',
    })

    print("    [Created fail2ban_wiki.pdf]")
    print("==> Done!")

if __name__ == "__main__":
    main()
