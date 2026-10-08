"""Wrap site/index.html (page body, no skeleton) into docs/index.html, the GitHub Pages site."""
import os
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
body = open(os.path.join(HERE, "site", "index.html"), encoding="utf-8").read()
head = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="Zero-shot AI-text detection that runs on your own computer. 92.33% on the official RAID test (88.99% with attacks), the highest zero-shot score, ahead of Binoculars (78.98%).">
<meta property="og:title" content="Detect Law">
<meta property="og:description" content="Zero-shot AI-text detection that runs on your own computer. 92.33% on the official RAID test (88.99% with attacks), the highest zero-shot score, ahead of Binoculars (78.98%).">
<style>[hidden]{display:none!important} img{max-width:100%}</style>
"""
title_end = body.index("</style>") + len("</style>")
html = head + body[:title_end] + "\n</head>\n<body>\n" + body[title_end:] + "\n</body>\n</html>\n"
open(os.path.join(HERE, "docs", "index.html"), "w", encoding="utf-8").write(html)
print("wrote docs/index.html", len(html), "bytes")
