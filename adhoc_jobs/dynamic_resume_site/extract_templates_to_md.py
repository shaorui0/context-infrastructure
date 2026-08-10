#!/usr/bin/env python3
"""One-off: pull the hand-written article templates out of site/deep.html back
into content/*.md, so every long-form article has a single markdown source.

Run once. After this the templates are generated from md like every other
article, and the md files are what feeds both the site and the blog.
"""
import os, re, html as H

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, "site", "deep.html")

TARGETS = {
    "w-cs-doris":    ("content/case_study_doris.md",        "CASE STUDY", "案例研究"),
    "w-inc-p100":    ("content/incidents/w_p100.md",        "INCIDENT",   "事故"),
    "w-inc-qps":     ("content/incidents/w_tenant_qps.md",  "INCIDENT",   "事故"),
    "w-inc-refused": ("content/incidents/w_refused.md",     "INCIDENT",   "事故"),
    "w-dr-restore":  ("content/incidents/w_dr_restore.md",  "RECOVERY",   "恢复"),
}


def unwrap(s):
    """inline HTML -> markdown"""
    s = re.sub(r'<span class="fig">(.*?)</span>', r"**\1**", s, flags=re.S)
    s = re.sub(r"<strong>(.*?)</strong>", r"**\1**", s, flags=re.S)
    s = re.sub(r"<b>(.*?)</b>", r"**\1**", s, flags=re.S)
    s = re.sub(r"<em>(.*?)</em>", r"*\1*", s, flags=re.S)
    s = re.sub(r"<i>(.*?)</i>", r"*\1*", s, flags=re.S)
    s = re.sub(r"<code>(.*?)</code>", r"`\1`", s, flags=re.S)
    s = re.sub(r'<a [^>]*href=[\'"]([^\'"]+)[\'"][^>]*>(.*?)</a>', r"\2", s, flags=re.S)  # links are re-emitted by the builder
    s = re.sub(r"<[^>]+>", "", s)
    s = H.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def body_to_md(frag):
    out = []
    # drop the header block the builder regenerates from META
    frag = re.sub(r'<div class="kick.*?</div>', "", frag, flags=re.S)
    frag = re.sub(r'<h1>.*?</h1>', "", frag, flags=re.S)
    frag = re.sub(r'<p class="standfirst">.*?</p>', "", frag, flags=re.S)
    frag = re.sub(r'<div class="tags">.*?</div>', "", frag, flags=re.S)

    for m in re.finditer(r"<(h2|h3|p|ul|ol|blockquote)\b[^>]*>(.*?)</\1>", frag, flags=re.S):
        tag, inner = m.group(1), m.group(2)
        if tag == "h2":
            out.append("## " + unwrap(inner))
        elif tag == "h3":
            out.append("### " + unwrap(inner))
        elif tag == "p":
            t = unwrap(inner)
            if t:
                out.append(t)
        elif tag == "blockquote":
            for p in re.findall(r"<p>(.*?)</p>", inner, flags=re.S) or [inner]:
                t = unwrap(p)
                if t:
                    out.append("> " + t)
        else:
            bullet = "- " if tag == "ul" else None
            for i, li in enumerate(re.findall(r"<li>(.*?)</li>", inner, flags=re.S), 1):
                t = unwrap(li)
                if t:
                    out.append((bullet or "%d. " % i) + t)
    return "\n\n".join(out)


def main():
    site = open(SITE, encoding="utf-8").read()
    # titles / subs live in the hand-written WRITINGS array
    warr = site.split("var WRITINGS = [", 1)[1].split("\n];", 1)[0]
    meta = {}
    for blk in re.finditer(
        r'id:"([\w-]+)",.*?title:\{en:"(.*?)", cn:"(.*?)"\}.*?sub:\{en:"(.*?)",\s*cn:"(.*?)"\}',
        warr, flags=re.S):
        meta[blk.group(1)] = dict(title_en=blk.group(2), title_cn=blk.group(3),
                                  sub_en=blk.group(4), sub_cn=blk.group(5))

    for wid, (rel, kick_en, kick_cn) in TARGETS.items():
        m = meta.get(wid)
        if not m:
            print("NO META:", wid); continue
        bodies = {}
        for lang in ("en", "cn"):
            t = re.search(r'<template id="%s-%s">(.*?)</template>' % (wid, lang), site, flags=re.S)
            if not t:
                print("NO TEMPLATE:", wid, lang); continue
            bodies[lang] = body_to_md(t.group(1))
        path = os.path.join(HERE, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("# META\n")
            f.write("id: %s\n" % wid)
            f.write("kicker_en: %s\nkicker_cn: %s\n" % (kick_en, kick_cn))
            f.write("title_en: %s\ntitle_cn: %s\n" % (m["title_en"], m["title_cn"]))
            f.write("sub_en: %s\nsub_cn: %s\n" % (m["sub_en"], m["sub_cn"]))
            f.write("domains: []\n\n")
            f.write("# EN\n\n" + bodies.get("en", "") + "\n\n")
            f.write("# CN\n\n" + bodies.get("cn", "") + "\n")
        print("wrote %-34s (%d/%d chars en/cn)" % (rel, len(bodies.get("en","")), len(bodies.get("cn",""))))


if __name__ == "__main__":
    main()
