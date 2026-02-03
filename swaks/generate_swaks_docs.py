#!/usr/bin/env python3

import requests
import subprocess
import os

POD_URL = (
    "https://raw.githubusercontent.com/jetmore/swaks/"
    "refs/tags/v20240103.0/doc/base.pod"
)

def main():
    # 1) Fetch the .pod file
    response = requests.get(POD_URL, timeout=30)
    response.raise_for_status()
    
    pod_file = "swaks_reference.pod"
    with open(pod_file, "wb") as f:
        f.write(response.content)

    # 2) Use Perl's pod2html to convert .pod -> .html
    #    (Requires Perl installed and pod2html available)
    html_file = "swaks_reference.html"
    subprocess.run([
        "pod2html",
        "--infile", pod_file,
        "--outfile", html_file
    ], check=True)

    # pod2html often injects extra files like pod2htmd.tmp etc. You can clean them up if you like:
    # Just remove them if they appear
    for extra_file in ("pod2htmd.tmp", "pod2htmi.tmp"):
        if os.path.exists(extra_file):
            os.remove(extra_file)

    # 3) Convert the HTML -> PDF using wkhtmltopdf
    #    (Requires wkhtmltopdf installed)
    pdf_file = "swaks_reference.pdf"
    subprocess.run(["wkhtmltopdf", html_file, pdf_file], check=True)

    print(f"Success! Generated PDF: {pdf_file}")

if __name__ == "__main__":
    main()
