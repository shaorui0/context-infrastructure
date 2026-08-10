#!/usr/bin/env python3
"""Export the long-form articles to the Hexo blog as bilingual post pairs.

Source of truth stays `content/*.md` (the same files build_content.py reads).
This script only ever writes into the blog's `source/_posts/`, one file per
language, and prints the canonical public URL of each so the resume site can
link out instead of embedding the text.

    python3 export_to_blog.py --list          # show what would be written + URLs
    python3 export_to_blog.py --write         # write the posts (draft by default)
    python3 export_to_blog.py --write --publish   # same, but not marked draft

Naming follows the blog's existing convention, which the permalink depends on:
    source/_posts/<date>_<slug>_{en,zh}.md
      -> https://shaorui0.github.io/tech/YYYY/MM/DD/<date>_<slug>_{en,zh}/
Changing a filename changes a published URL, so slugs are pinned in SLUGS below.
"""
import os, re, sys, json, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
BLOG = os.path.abspath(os.path.join(HERE, "..", "..", "work-contexts", "toy-proj", "blog-system"))
# two sites since 2026-08-04: Chinese at /tech/, English at /tech-en/
POSTS = {"zh": os.path.join(BLOG, "source", "_posts"),
         "en": os.path.join(BLOG, "source-en", "_posts")}
BASE_URL = {"zh": "https://shaorui0.github.io/tech",
            "en": "https://shaorui0.github.io/tech-en"}

# id -> (date, slug, category_en, category_zh). Pinned: a slug change breaks a live URL.
SLUGS = {
    "w-cs-doris":      ("2026-08-03", "rebuilding-a-5b-row-event-store",   "Data Platform",        "数据平台"),
    "w-inc-p100":      ("2026-08-03", "the-p100-that-was-exactly-one-second", "Incidents",          "事故复盘"),
    "w-inc-qps":       ("2026-08-03", "order-of-operations-under-fire",     "Incidents",            "事故复盘"),
    "w-inc-refused":   ("2026-08-03", "refused-is-not-timeout",             "Incidents",            "事故复盘"),
    "w-dr-restore":    ("2026-08-03", "restoring-5b-rows-without-touching-prod", "Incidents",       "事故复盘"),
    "w-p-fanout":      ("2026-08-03", "fan-out-is-the-floor",              "Data Platform",        "数据平台"),
    "w-p-routing":     ("2026-08-03", "engine-level-query-routing",        "Data Platform",        "数据平台"),
    "w-p-elastic":     ("2026-08-03", "designing-the-elastic-compute-tier","Data Platform",        "数据平台"),
    "w-p-vm":          ("2026-08-03", "replacing-prometheus-federation",   "Observability",        "可观测性"),
    "w-p-alertgov":    ("2026-08-03", "alert-governance",                  "Observability",        "可观测性"),
    "w-p-upgrade":     ("2026-08-03", "kubernetes-upgrade-engineering",    "Production Engineering", "生产工程"),
    "w-p-jenkins":     ("2026-08-03", "what-knows-jenkins-actually-tests", "Production Engineering", "生产工程"),
    "w-p-bkc":         ("2026-08-03", "compiling-a-document-into-a-control-loop", "Production Engineering", "生产工程"),
    "w-p-agentops":     ("2026-08-03", "sre-oncall-triage-harness",        "AI Agents",            "AI Agent"),
    "w-inc-oom":       ("2026-08-03", "zombie-system-tables-subsecond-oom","Incidents",            "事故复盘"),
    "w-v-capabilities":("2026-08-03", "what-i-understand-sre-to-require",  "Perspective",          "视角"),
    "w-v-mapping":     ("2026-08-03", "an-audit-of-my-own-radar",          "Perspective",          "视角"),
    "w-v-next":        ("2026-08-03", "what-i-know-i-cant-do-yet",         "Perspective",          "视角"),
    "w-v-agents":      ("2026-08-03", "sre-in-the-age-of-ai-agents",       "AI Agents",            "AI Agent"),
    # already present in the blog as drafts — do not duplicate, reuse these URLs
    "w-g-slo":         ("2026-07-20", "slo-top-down-monitoring",           None, None),
    "w-g-infravalue":  ("2026-07-20", "infra-engineer-value-cloud-philosophy", None, None),
}

# Articles already living in the blog (single-language files, no _en/_zh suffix pair)
PREEXISTING = {
    "w-g-slo":        {"zh": "2026-07-20_slo-top-down-monitoring_zh"},
    "w-g-infravalue": {"zh": "2026-07-20_infra-engineer-value-cloud-philosophy_zh"},
}

FILES = [
    "content/case_study_doris.md",
    "content/incidents/w_p100.md",
    "content/incidents/w_tenant_qps.md",
    "content/incidents/w_refused.md",
    "content/incidents/w_dr_restore.md",
    "content/projects/p_vm_platform.md",
    "content/projects/p_k8s_upgrade.md",
    "content/projects/p_engine_routing.md",
    "content/projects/p_io_fanout.md",
    "content/projects/p_elastic_compute.md",
    "content/projects/p_alert_gov.md",
    "content/projects/p_jenkins.md",
    "content/projects/p_agentops.md",
    "content/projects/p_bkc.md",
    "content/incidents/w_zombie_oom.md",
    "content/perspectives/v1_sre_capabilities.md",
    "content/perspectives/v2_current_mapping.md",
    "content/perspectives/v3_next.md",
    "content/perspectives/v4_ai_agents.md",
    "content/growth/g_slo_topdown.md",
    "content/growth/g_infra_value.md",
]

TAGS = {
    "en": {"Data Platform": ["Apache Doris", "ClickHouse", "OLAP", "Storage Engine", "SRE"],
           "Observability": ["Observability", "VictoriaMetrics", "Prometheus", "SLO", "SRE"],
           "Production Engineering": ["Kubernetes", "CI/CD", "Infrastructure as Code", "SRE"],
           "AI Agents": ["AI Agents", "AgentOps", "LLM", "SRE"],
           "Incidents": ["Incident Response", "Root Cause Analysis", "SRE"],
           "Perspective": ["Career", "SRE", "Engineering Judgement"]},
    "zh": {"数据平台": ["Apache Doris", "ClickHouse", "OLAP", "存储引擎", "SRE"],
           "可观测性": ["可观测性", "VictoriaMetrics", "Prometheus", "SLO", "SRE"],
           "生产工程": ["Kubernetes", "CI/CD", "基础设施即代码", "SRE"],
           "AI Agent": ["AI Agent", "AgentOps", "LLM", "SRE"],
           "事故复盘": ["事故复盘", "根因分析", "SRE"],
           "视角": ["职业", "SRE", "工程判断"]},
}


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


def yaml_str(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


def front_matter(title, date, desc, cat, tags, publish):
    out = ["---", "title: " + yaml_str(title), "date: " + date]
    if desc:
        out.append("description: " + yaml_str(desc))
    out.append("tags:")
    out += ["  - " + t for t in tags]
    out.append("categories:")
    out.append("  - " + cat)
    if not publish:
        out.append("draft: true")
    out += ["---", ""]
    return "\n".join(out)


def url_for(basename, lang):
    d = basename[:10].replace("-", "/")
    return "%s/%s/%s/" % (BASE_URL[lang], d, basename)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--publish", action="store_true")
    args = ap.parse_args()

    urls, wrote = {}, 0
    for rel in FILES:
        path = os.path.join(HERE, rel)
        if not os.path.exists(path):
            print("SKIP (missing):", rel); continue
        meta, en, cn = parse(path)
        wid = meta.get("id")
        if wid not in SLUGS:
            print("SKIP (no slug pinned):", wid or rel); continue
        date, slug, cat_en, cat_zh = SLUGS[wid]

        if wid in PREEXISTING:
            urls[wid] = {lang: url_for(bn, lang) for lang, bn in PREEXISTING[wid].items()}
            print("REUSE %-18s %s" % (wid, urls[wid]["zh"]))
            continue

        entry, files = {}, {}
        for lang, body, title, sub, cat in (
            ("en", en, meta.get("title_en", ""), meta.get("sub_en", ""), cat_en),
            ("zh", cn, meta.get("title_cn", ""), meta.get("sub_cn", ""), cat_zh),
        ):
            if not body:
                continue
            basename = "%s_%s_%s" % (date, slug, lang)
            entry[lang] = url_for(basename, lang)
            files[lang] = (basename, front_matter(title, date, sub, cat, TAGS[lang][cat], args.publish), body)

        if args.write:
            for lang, (basename, fm, body) in files.items():
                other = "en" if lang == "zh" else "zh"
                banner = ""
                if other in files:   # same article on the sibling site; phrase it in THIS page's language
                    banner = ("> 英文版：[English](%s)\n\n" % url_for(files[other][0], other)
                              if lang == "zh" else
                              "> Also in Chinese: [中文版](%s)\n\n" % url_for(files[other][0], other))
                with open(os.path.join(POSTS[lang], basename + ".md"), "w", encoding="utf-8") as f:
                    f.write(fm + banner + body + "\n")
                wrote += 1
        urls[wid] = entry
        print("%-18s %s" % (wid, entry.get("en", entry.get("zh"))))

    with open(os.path.join(HERE, "blog_urls.json"), "w", encoding="utf-8") as f:
        json.dump(urls, f, ensure_ascii=False, indent=1)
    print("\n%d articles mapped -> blog_urls.json%s" % (len(urls), "; %d files written" % wrote if args.write else " (dry run)"))


if __name__ == "__main__":
    main()
