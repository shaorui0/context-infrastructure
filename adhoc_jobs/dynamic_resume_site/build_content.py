#!/usr/bin/env python3
"""Inject the article index into site/deep.html (the drill-down resume).

Since 2026-08-03 the full article text lives on the blog (shaorui0.github.io/tech),
generated from these same md files by export_to_blog.py. This script therefore
injects only the writing INDEX (title + standfirst + outbound URL) — no article
bodies — so there is exactly one copy of every article.

site/index.html is the hand-written landing page and is NOT touched by this script.

Each content md has sections: `# META` (key: value lines), `# EN`, `# CN`, `# SOURCES`.
Generates <template id="{id}-en|-cn"> blocks between GEN:TEMPLATES markers and
GEN_WRITINGS entries between GEN:WRITINGS markers. Idempotent (regenerates fully).

Markdown subset supported: ## h2, ### h3, - / 1. lists, > blockquote, **bold**,
`code`, plain paragraphs. Numbers wrapped in **...** stay <strong>; no external deps.
"""
import os, re, json, html, sys

HERE = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(HERE, "site", "deep.html")
URLS = os.path.join(HERE, "blog_urls.json")   # written by export_to_blog.py

FILES = [
    ("content/case_study_doris.md",           "case"),
    ("content/incidents/w_p100.md",           "incident"),
    ("content/incidents/w_tenant_qps.md",     "incident"),
    ("content/incidents/w_refused.md",        "incident"),
    ("content/incidents/w_dr_restore.md",     "incident"),
    ("content/projects/p_vm_platform.md",     "project"),
    ("content/projects/p_k8s_upgrade.md",     "project"),
    # REMOVED 2026-08-03: the auto traffic-switch control plane is a colleague's system, not Rui's
    # (confirmed in senior_sre_interview_prep/90_cross_cutting/number_baseline.md §5.1).
    # The md stays on disk for reference; it must not ship on the public site.
    # ("content/projects/p_traffic_switch.md",  "project"),
    ("content/projects/p_engine_routing.md",  "project"),
    ("content/projects/p_io_fanout.md",       "project"),
    ("content/projects/p_elastic_compute.md", "project"),
    ("content/projects/p_alert_gov.md",       "project"),
    ("content/projects/p_jenkins.md",         "project"),
    ("content/projects/p_agentops.md",        "project"),
    ("content/projects/p_bkc.md",             "project"),
    ("content/incidents/w_zombie_oom.md",     "incident"),
    ("content/perspectives/v1_sre_capabilities.md", "perspective"),
    ("content/perspectives/v2_current_mapping.md",  "perspective"),
    ("content/perspectives/v3_next.md",             "perspective"),
    ("content/perspectives/v4_ai_agents.md",        "perspective"),
    ("content/growth/g_slo_topdown.md",              "philosophy"),
    ("content/growth/g_infra_value.md",              "philosophy"),
]

def parse(path):
    txt = open(path, encoding="utf-8").read()
    parts = re.split(r"^# (META|EN|CN|SOURCES)\s*$", txt, flags=re.M)
    sec = {}
    for i in range(1, len(parts) - 1, 2):
        sec[parts[i]] = parts[i + 1].strip()
    meta = {}
    for line in sec.get("META", "").splitlines():
        m = re.match(r"^([\w_]+):\s*(.+)$", line.strip())
        if m:
            meta[m.group(1)] = m.group(2).strip()
    return meta, sec.get("EN", ""), sec.get("CN", "")

def inline(s):
    s = html.escape(s, quote=False)
    # stash code spans first: an asterisk inside one (`SELECT *`) must never be
    # read as emphasis and paired with a later asterisk in the same line
    codes = []
    def stash_code(m):
        codes.append(m.group(1))
        return "\x01CODE%d\x01" % (len(codes) - 1)
    s = re.sub(r"`([^`]+)`", stash_code, s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\*([^*\n]+)\*", r"<em>\1</em>", s)
    for i, c in enumerate(codes):
        s = s.replace("\x01CODE%d\x01" % i, "<code>" + c + "</code>")
    return s

def md2html(md):
    # extract fenced blocks first (```mermaid / ```lang)
    fences = []
    def stash(m):
        lang = (m.group(1) or "").strip()
        body = m.group(2)
        if lang == "mermaid":
            h = '<pre class="mermaid">' + html.escape(body) + '</pre>'
        else:
            h = '<pre class="codeblock"><code>' + html.escape(body) + '</code></pre>'
        fences.append(h)
        return "\x00FENCE%d\x00" % (len(fences) - 1)
    md = re.sub(r"```([\w-]*)\n(.*?)```", stash, md, flags=re.S)

    # GFM pipe tables -> <table>, stashed like fences so the line loop never sees them
    def is_sep(line):
        return bool(re.match(r"^\|[\s:|-]+\|$", line.strip())) and "-" in line

    def cells(line):
        parts = line.strip().split("|")
        return [c.strip() for c in parts[1:-1]] if len(parts) >= 3 else []

    lines, out_lines, i = md.split("\n"), [], 0
    while i < len(lines):
        cur = lines[i].strip()
        if cur.startswith("|") and cur.endswith("|") and i + 1 < len(lines) and is_sep(lines[i + 1]):
            head = cells(lines[i])
            i += 2
            body = []
            while i < len(lines) and lines[i].strip().startswith("|") and lines[i].strip().endswith("|"):
                body.append(cells(lines[i]))
                i += 1
            h = '<div class="mdtable-wrap"><table class="mdtable"><thead><tr>'
            h += "".join("<th>" + inline(c) + "</th>" for c in head)
            h += "</tr></thead><tbody>"
            for row in body:
                h += "<tr>" + "".join("<td>" + inline(c) + "</td>" for c in row) + "</tr>"
            h += "</tbody></table></div>"
            fences.append(h)
            out_lines.append("\x00FENCE%d\x00" % (len(fences) - 1))
            continue
        out_lines.append(lines[i])
        i += 1
    md = "\n".join(out_lines)
    out, buf, mode = [], [], None  # mode: p | ul | ol | bq
    def flush():
        nonlocal buf, mode
        if not buf: return
        if mode == "ul":
            out.append("<ul>" + "".join("<li>" + inline(b) + "</li>" for b in buf) + "</ul>")
        elif mode == "ol":
            out.append("<ol>" + "".join("<li>" + inline(b) + "</li>" for b in buf) + "</ol>")
        elif mode == "bq":
            out.append("<blockquote><p>" + inline(" ".join(buf)) + "</p></blockquote>")
        else:
            out.append("<p>" + inline(" ".join(buf)) + "</p>")
        buf, mode = [], None
    for raw in md.splitlines():
        line = raw.rstrip()
        if not line.strip():
            flush(); continue
        m3 = re.match(r"^###\s+(.+)$", line)
        m2 = re.match(r"^##\s+(.+)$", line)
        ml = re.match(r"^[-*]\s+(.+)$", line)
        mo = re.match(r"^\d+[.)]\s+(.+)$", line)
        mq = re.match(r"^>\s?(.*)$", line)
        if m2:
            flush(); out.append("<h2>" + inline(m2.group(1)) + "</h2>")
        elif m3:
            flush(); out.append("<h3>" + inline(m3.group(1)) + "</h3>")
        elif ml:
            if mode != "ul": flush(); mode = "ul"
            buf.append(ml.group(1))
        elif mo:
            if mode != "ol": flush(); mode = "ol"
            buf.append(mo.group(1))
        elif mq:
            if mode != "bq": flush(); mode = "bq"
            buf.append(mq.group(1))
        else:
            if mode in ("ul", "ol") and re.match(r"^\s{2,}", raw):
                buf[-1] += " " + line.strip()   # continuation of list item
            else:
                if mode != "p": flush(); mode = "p"
                buf.append(line.strip())
    flush()
    htm = "\n  ".join(out)
    for i, f in enumerate(fences):
        marker = "\x00FENCE%d\x00" % i
        htm = htm.replace("<p>" + marker + "</p>", f).replace(marker, f)
    return htm

def article(meta, body_md, lang, group):
    kick = meta.get("kicker_en" if lang == "en" else "kicker_cn", "")
    title = meta.get("title_en" if lang == "en" else "title_cn", "")
    sub = meta.get("sub_en" if lang == "en" else "sub_cn", "")
    color = "var(--petrol)" if group in ("perspective", "philosophy") else "var(--amber)"
    doms = [d.strip() for d in meta.get("domains", "").strip("[]").split(",") if d.strip()]
    chips = "".join('<span class="chip">%s</span>' % html.escape(d) for d in doms)
    return (
        '<article>\n'
        '  <div class="kick eyebrow" style="color:%s">%s</div>\n' % (color, html.escape(kick)) +
        '  <h1>%s</h1>\n' % inline(title) +
        '  <p class="standfirst">%s</p>\n' % inline(sub) +
        ('  <div class="tags">%s</div>\n' % chips if chips else "") +
        "  " + md2html(body_md) + "\n"
        "</article>"
    )

def main():
    blog = {}
    if os.path.exists(URLS):
        blog = json.load(open(URLS, encoding="utf-8"))
    else:
        print("WARNING: blog_urls.json missing — run export_to_blog.py first")

    entries, missing = [], []
    for rel, group in FILES:
        path = os.path.join(HERE, rel)
        if not os.path.exists(path):
            print("SKIP (missing):", rel); continue
        meta, en, cn = parse(path)
        wid = meta.get("id")
        if not wid or not en or not cn:
            print("SKIP (bad structure):", rel); continue
        u = blog.get(wid, {})
        if not u:
            missing.append(wid)
        entries.append({
            "id": wid, "group": group,
            "kicker": {"en": meta.get("kicker_en", ""), "cn": meta.get("kicker_cn", "")},
            "title":  {"en": meta.get("title_en", ""),  "cn": meta.get("title_cn", "")},
            "sub":    {"en": meta.get("sub_en", ""),    "cn": meta.get("sub_cn", "")},
            # outbound: the article itself lives on the blog. cn falls back to en and vice versa.
            "url":    {"en": u.get("en") or u.get("zh", ""), "cn": u.get("zh") or u.get("en", "")},
        })
        print("OK: %-42s -> %s" % (rel, u.get("en") or u.get("zh") or "NO URL"))

    site = open(SITE, encoding="utf-8").read()
    # article bodies no longer ship with the site
    site = re.sub(
        r"<!-- GEN:TEMPLATES START -->.*?<!-- GEN:TEMPLATES END -->",
        "<!-- GEN:TEMPLATES START -->\n<!-- article bodies live on the blog; see export_to_blog.py -->\n<!-- GEN:TEMPLATES END -->",
        site, flags=re.S)
    site = re.sub(
        r"/\* GEN:WRITINGS START \*/.*?/\* GEN:WRITINGS END \*/",
        "/* GEN:WRITINGS START */\nvar GEN_WRITINGS = " + json.dumps(entries, ensure_ascii=False, indent=1) + ";\n/* GEN:WRITINGS END */",
        site, flags=re.S)
    cases_path = os.path.join(HERE, "content", "integration", "case_cards.json")
    if os.path.exists(cases_path):
        cases = json.load(open(cases_path, encoding="utf-8"))
        site = re.sub(
            r"/\* GEN:CASES START \*/.*?/\* GEN:CASES END \*/",
            "/* GEN:CASES START */\nvar CASES = " + json.dumps(cases, ensure_ascii=False) + ";\n/* GEN:CASES END */",
            site, flags=re.S)
        print("Injected %d case cards" % len(cases))
    open(SITE, "w", encoding="utf-8").write(site)
    if missing:
        print("NO BLOG URL for:", ", ".join(missing))
    print("Injected index of %d articles (0 bodies) into %s" % (len(entries), SITE))


if __name__ == "__main__":
    main()
