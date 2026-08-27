#!/usr/bin/env python3
# build-pdf.py — render Richard_Wooding_CV.pdf from index.html.
#
# index.html is the single source of truth for CV content. This script reads the
# content back out of it, re-lays it out in a plain print/ATS format (print.css),
# and prints that to PDF with headless Chrome. Run it after editing index.html so
# the downloadable CV never drifts from the site.
#
# Usage:
#   build-pdf.py [--chrome PATH] [--out FILE] [--keep-html]
#     --chrome     Chrome/Chromium binary (default: the macOS Google Chrome path)
#     --out        output PDF (default: <script dir>/Richard_Wooding_CV.pdf)
#     --keep-html  keep the intermediate print HTML and report its path
#
# Extraction keys off the class names index.html already uses (gl-tl-item,
# gl-def, ...). It asserts on anything it expects and cannot find, so a markup
# change in index.html fails the build loudly instead of silently dropping a
# section from the PDF.

import argparse
import html
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
from html.parser import HTMLParser

MAC_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
        "link", "meta", "param", "source", "track", "wbr"}
INLINE_KEEP = {"strong", "em", "b", "i", "a", "br"}


class Node:
    def __init__(self, tag, attrs=None):
        self.tag = tag
        self.attrs = dict(attrs or {})
        self.children = []
        self.text = ""

    @property
    def classes(self):
        return self.attrs.get("class", "").split()

    def walk(self):
        for child in self.children:
            yield child
            yield from child.walk()

    def find(self, tag=None, cls=None, id=None):
        return next(iter(self.find_all(tag, cls, id, limit=1)), None)

    def find_all(self, tag=None, cls=None, id=None, limit=None):
        out = []
        for node in self.walk():
            if node.tag == "#text":
                continue
            if tag and node.tag != tag:
                continue
            if cls and cls not in node.classes:
                continue
            if id and node.attrs.get("id") != id:
                continue
            out.append(node)
            if limit and len(out) == limit:
                break
        return out

    def children_by(self, tag=None, cls=None):
        return [c for c in self.children
                if (not tag or c.tag == tag) and (not cls or cls in c.classes)]


class Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root")
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Node(tag, attrs))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        node = Node("#text")
        node.text = data
        self.stack[-1].children.append(node)


def parse(path):
    tree = Tree()
    tree.feed(path.read_text())
    return tree.root


def inner_html(node, skip=()):
    if node is None:
        return ""
    parts = []
    for child in node.children:
        if child.tag == "#text":
            parts.append(html.escape(child.text))
        elif child.tag in ("svg", "script", "style") or any(c in child.classes for c in skip):
            continue
        elif child.tag in INLINE_KEEP:
            attrs = ""
            if child.tag == "a" and "href" in child.attrs:
                attrs = f' href="{html.escape(child.attrs["href"], quote=True)}"'
            parts.append(f"<{child.tag}{attrs}>{inner_html(child, skip)}</{child.tag}>")
        else:
            parts.append(inner_html(child, skip))
    return " ".join("".join(parts).split())


def plain(node, skip=()):
    if node is None:
        return ""
    parts = []
    for child in node.children:
        if child.tag == "#text":
            parts.append(child.text)
        elif child.tag in ("svg", "script", "style") or any(c in child.classes for c in skip):
            continue
        else:
            parts.append(plain(child, skip))
    return " ".join("".join(parts).split())


def require(value, what):
    assert value, f"build-pdf: could not find {what} in index.html"
    return value


def timeline(section):
    entries = []
    for item in require(section.find_all(cls="gl-tl-item"), "timeline items"):
        title = require(item.find(cls="gl-tl-title"), "a timeline title")
        org = title.find(cls="gl-tl-org")
        role = plain(title, skip=("gl-tl-org",)).rstrip(" ·")
        note = item.find(cls="gl-tl-note")
        bullets = item.find("ul")
        entries.append({
            "role": role,
            "org": plain(org) if org else "",
            "date": plain(item.find(cls="gl-tl-date")),
            "note": inner_html(note) if note else "",
            "bullets": [inner_html(li) for li in bullets.children_by("li")] if bullets else [],
        })
    return entries


def tagline(root):
    # The hero eyebrow is styled lowercase ("ai & mcp tooling"); <title> carries
    # the same words with their real casing, so take it from there.
    title = plain(require(root.find("title"), "the document title"))
    return title.split("—", 1)[1].strip() if "—" in title else title


def extract(root):
    hero = require(root.find(cls="gl-hero"), "the hero section")
    contact = [inner_html(li) for li in require(hero.find(cls="gl-contact"), "the contact list").children_by("li")]
    projects = []
    for card in require(root.find(id="projects"), "the projects section").find_all(cls="gl-card"):
        body = [p for p in card.find_all("p") if "gl-hint" not in p.classes]
        link = card.find("a")
        projects.append({
            "name": plain(card.find("h3")),
            "blurb": inner_html(body[0]) if body else "",
            "url": link.attrs.get("href", "") if link else "",
        })
    skills = []
    for group in require(root.find(id="skills"), "the skills section").find_all(cls="gl-def"):
        skills.append({
            "label": plain(group.find("dt")),
            "items": " · ".join(plain(b) for b in group.find_all(cls="gl-lang")),
        })
    talks = []
    for card in require(root.find(id="speaking"), "the speaking section").find_all(cls="gl-card"):
        talks.append({
            "name": plain(card.find("h3")),
            "blurb": inner_html(card.find("p")),
        })
    return {
        "name": plain(hero.find("h1")).rstrip("."),
        "tagline": tagline(root),
        "contact": contact,
        "summary": [inner_html(require(hero.find("p", cls="sub"), "the hero summary")),
                    inner_html(require(root.find(id="summary"), "the summary section").find(cls="gl-lede"))],
        "experience": timeline(require(root.find(id="experience"), "the experience section")),
        "projects": projects,
        "skills": skills,
        "talks": talks,
        "education": timeline(require(root.find(id="education"), "the education section")),
    }


def entry_html(entry, bullets=True):
    out = ['<div class="entry"><div class="entry-head"><p class="role">', html.escape(entry["role"])]
    if entry["org"]:
        out.append(f' · <span class="org">{html.escape(entry["org"])}</span>')
    out.append(f'</p><span class="date">{html.escape(entry["date"])}</span></div>')
    if entry["note"]:
        out.append(f'<p class="note">{entry["note"]}</p>')
    if bullets and entry["bullets"]:
        out.append("<ul>" + "".join(f"<li>{b}</li>" for b in entry["bullets"]) + "</ul>")
    out.append("</div>")
    return "".join(out)


def render(cv, css):
    parts = [
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">",
        f"<title>{html.escape(cv['name'])} — CV</title><style>{css}</style></head><body>",
        f"<h1>{html.escape(cv['name'])}</h1>",
        f"<p class=\"tagline\">{html.escape(cv['tagline'])}</p>",
        f"<p class=\"contact\">{' &nbsp;·&nbsp; '.join(cv['contact'])}</p>",
        "<h2>Professional summary</h2>",
        *(f"<p>{p}</p>" for p in cv["summary"]),
        "<h2>Experience</h2>",
        *(entry_html(e) for e in cv["experience"]),
        "<h2>Open source projects</h2>",
    ]
    for project in cv["projects"]:
        link = (f' <a class="project-link" href="{html.escape(project["url"], quote=True)}">'
                f'{html.escape(project["url"].replace("https://", ""))}</a>') if project["url"] else ""
        parts.append(f'<p class="project"><span class="project-name">{html.escape(project["name"])}</span>'
                     f'{link}<br>{project["blurb"]}</p>')
    parts.append("<h2>Skills &amp; technologies</h2>")
    for skill in cv["skills"]:
        parts.append(f'<p class="skill-row"><span class="skill-label">{html.escape(skill["label"])}:</span>'
                     f'{html.escape(skill["items"])}</p>')
    parts.append("<h2>Speaking</h2>")
    for talk in cv["talks"]:
        parts.append(f'<p class="project"><span class="project-name">{html.escape(talk["name"])}</span><br>{talk["blurb"]}</p>')
    parts.append("<h2>Education</h2>")
    parts.extend(entry_html(e, bullets=False) for e in cv["education"])
    parts.append("</body></html>")
    return "".join(parts)


def print_pdf(chrome, page, out):
    # --no-pdf-header-footer is the modern spelling; older Chrome builds only
    # know --print-to-pdf-no-header, so fall back rather than emit a PDF with
    # "file:///..." stamped in the margins.
    for flag in ("--no-pdf-header-footer", "--print-to-pdf-no-header"):
        result = subprocess.run(
            [chrome, "--headless", "--disable-gpu", "--no-sandbox", flag,
             f"--print-to-pdf={out}", "--virtual-time-budget=10000", page.as_uri()],
            capture_output=True, text=True)
        if result.returncode == 0 and out.exists():
            return
    sys.exit(f"build-pdf: Chrome failed to print\n{result.stderr.strip()}")


def content_date(here):
    result = subprocess.run(["git", "log", "-1", "--format=%cd", "--date=format:%Y%m%d",
                             "--", "index.html"], cwd=here, capture_output=True, text=True)
    stamp = result.stdout.strip()
    return stamp if len(stamp) == 8 and stamp.isdigit() else "20240101"


def normalize(pdf, date):
    # Chrome stamps the wall-clock time, so every rebuild would differ even when
    # the content didn't. Pin it to the content's own commit date; the
    # replacement is the same byte length, so the xref offsets stay valid.
    raw = pdf.read_bytes()
    pdf.write_bytes(re.sub(rb"D:\d{14}\+00'00'", f"D:{date}000000+00'00'".encode(), raw))


def main():
    here = pathlib.Path(__file__).resolve().parent
    ap = argparse.ArgumentParser()
    ap.add_argument("--chrome", default=MAC_CHROME)
    ap.add_argument("--out", type=pathlib.Path, default=here / "Richard_Wooding_CV.pdf")
    ap.add_argument("--keep-html", action="store_true")
    args = ap.parse_args()

    chrome = args.chrome if pathlib.Path(args.chrome).exists() else shutil.which(args.chrome)
    if not chrome:
        sys.exit(f"build-pdf: Chrome not found at {args.chrome} — pass --chrome PATH")

    cv = extract(parse(here / "index.html"))
    page_html = render(cv, (here / "print.css").read_text())

    workdir = pathlib.Path(tempfile.mkdtemp(prefix="cv-pdf-"))
    page = workdir / "print.html"
    page.write_text(page_html)
    out = args.out.resolve()
    print_pdf(chrome, page, out)
    normalize(out, content_date(here))
    if args.keep_html:
        print(f"  intermediate: {page}")
    else:
        shutil.rmtree(workdir)

    print(f"✓ {out.name} rebuilt from index.html "
          f"({len(cv['experience'])} roles, {len(cv['projects'])} projects, "
          f"{out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
