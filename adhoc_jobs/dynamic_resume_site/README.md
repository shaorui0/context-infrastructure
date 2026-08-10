# dynamic_resume_site

面向 recruiter / hiring manager 的个人动态简历站点。四层钻取（resume → 九轴雷达 → 域卡片 → thinking+evidence），内容即结构化数据，git 提交即能力快照。

## 站点结构（2026-07-31 起）

两页：

- `site/index.html` — **落地页**，karpathy.ai 形式（单栏、白底、无框架，宽 66rem）：居中 header（头像 + 名字 + 斜体 tagline + 链接）→ 时间线简历树（竖直 rail + 圆点 + 72px logo 方块，每格只写一段 summary + 一条深链，年份粒度）→ Bio → Featured writing → Pet projects。手写维护，`build_content.py` 不碰它。
  - 图片是可选 drop-in，缺文件自动 fallback 到字母：头像 `site/me.jpg`（fallback「RS」圆），公司 logo `site/logo-datavisor.png` / `site/logo-intel.png`（72×72，fallback「DV」「in」方块）
  - 正文用 `max-width:47rem` 限行宽，页面宽但不出现 120 字符的行
- `site/deep.html` — **deeper résumé**（原 index.html），四层钻取 L0→L3，中英双语。已改为纯白底（去掉 prefers-color-scheme 自动暗色），L0 简历与教育经历改成与落地页一致的时间线形式（period · 字母块 · 内容）。`build_content.py` 注入目标就是这个文件。

两页互链：落地页每条 bullet 指向 `deep.html#/en/w/<id>`，deep 页 header 有 `← Home`。

### build_content.py 的 markdown 子集（2026-08-03 补了两处）

- **GFM 管道表格**现在支持了（`| a | b |` + `|---|---|`），渲染成 `.mdtable`（横向可滚动，样式在 deep.html 的 head 里）。此前所有 `content/*.md` 里的表格都被渲染成一行管道符文本 —— 受影响的旧文已随本次重建修好（p_k8s_upgrade / p_bkc / g_slo_topdown / g_infra_value 等）。
- **行内 code 里的 `*` 不再被当强调符**（`` `SELECT *` `` 曾把它后面的 `*...*` 配对成斜体，吞掉中间整段格式）。修法是先把 code span 抽出占位再做 bold/em。


## 已上线（2026-08-03）

| 什么 | 地址 | 仓库 |
|---|---|---|
| **落地页（= 站点根，唯一入口）** | **https://shaorui0.github.io/** | `shaorui0/shaorui0.github.io`（master 根目录） |
| 深度简历 | https://shaorui0.github.io/deep.html | 同上 |
| 可打印 LaTeX 简历 | https://shaorui0.github.io/latex/{en,cn}.tex | 同上 |
| 21 篇长文（中英 40 个 URL） | https://shaorui0.github.io/tech/ | `shaorui0/tech`（gh-pages，hexo deploy） |
| 旧的 `/resume/` 链接 | 302 到根域（保留语言 hash） | `shaorui0/resume`（只剩一个跳转页） |

**没有 hub、没有卡片**：根域直接就是简历落地页；博客不做入口卡，靠页面里的「Blog / 博客」链接和 Featured writing 的 30 条外链进入。

**finance / life 已下线（2026-08-03）**：仓库转为私有于是 Pages 停止服务（API 关不掉 —— 那两个仓库的 `gh-pages` 就是默认分支，GitHub 拒绝 deactivate）。仓库、分支、内容全在，线上产物快照存于 `work-contexts/toy-proj/_published_backup/`（含恢复命令），Hexo 源码仍在 `blog-finance/`（8 篇）与 `blog-life/`（3 篇）。恢复 = 改回 public。

⚠️ **根域换成简历之后的连带修正**：页面里所有指向「博客」的裸域链接（8 处）原本是 `https://shaorui0.github.io`，换根之后全部变成自指，已改成 `/tech/`；pet projects 里「三条线（系统与 AI、市场、生活）的博客」也已改掉。**以后再动根域，先 grep 一遍裸域链接。**

**发布流程（改文章 → 上线）**

```bash
# 1. 编辑 content/*.md（唯一事实源）
python3 export_to_blog.py --write --publish   # 写博客文章 + 产出 blog_urls.json
python3 build_content.py                      # 把外链索引注入 site/deep.html
cd ../../work-contexts/toy-proj/blog-system && npx hexo deploy   # 发文章

# 2. 站点本身（HTML/样式/文案）变了：把两个文件推到根域仓库
#    clone https://github.com/shaorui0/shaorui0.github.io，cp site/{index,deep}.html 进去，commit push master
```

**凭据要点（踩过一次）**：`gh` 里同时有工作账号 `datavisorruishao`（active）和个人 `shaorui0`。git 走 osxkeychain 会拿到**工作账号**并 403。解法是在推送仓库里清空凭据链再挂一个运行时取 token 的 helper：

```bash
git config --local --add credential.helper ""   # 清空继承的链，关键
git config --local --add credential.helper '!f(){ echo username=x-access-token; echo "password=$(gh auth token --user shaorui0)"; };f'
git config --local user.email sr1054461216@gmail.com   # 别把工作邮箱写进公开仓库
```

⚠️ `shaorui0/tech` 的 gh-pages 历史里还有 40 个带工作邮箱的 commit（2026-04-15 及以前）。纯产物分支，重写零代价，待处理。

## 文章去哪了（2026-08-03 架构变更）

**长文全部搬到博客上了**，简历站只留索引 + 外链，`content/*.md` 是唯一事实源：

```
content/*.md  ──(build_content.py)──>  site/deep.html   索引：标题 + 一句话 + 外链
              └─(export_to_blog.py)─>  blog source/_posts/<date>_<slug>_{en,zh}.md
                                        └─ https://shaorui0.github.io/tech/YYYY/MM/DD/<basename>/
```

- `export_to_blog.py` 先跑（写文章 + 产出 `blog_urls.json`），`build_content.py` 后跑（读 json 注入外链）
- **slug 在 export_to_blog.py 里钉死**：改文件名 = 改已发布 URL，必须同步改 SLUGS 注释里的说明
- 站点两页的文章链接都按语言走（EN → `_en`，中文 → `_zh`），并在新标签打开
- deep.html 的 `#/xx/w/<id>` 老路由保留为**重定向**，跳到博客对应语言的文章
- 五篇原本只以 HTML 模板存在的文章（case study + 四篇事故）已用 `extract_templates_to_md.py` 反抽成 md；`content/case_study_ch_to_doris.md` 标记为 SUPERSEDED
- 副作用：deep.html 从 430KB 降到 216KB；离线双击打开时正文需要联网

## 目录

- `content_plan.md` — 内容总纲：架构、雷达分数、L3 清单、脱敏规则、数字口径（先读这个）
- `content/` — L3 成稿（case study、博客、事故叙事）
- `research/mining_notes.md` — 三线挖掘的判断性结论 + 事实源索引
- `prototype/dynamic-resume.jsx` — UI 原型（React + recharts，来自 Claude.ai，待修 years/location 两处事实错误）

## 状态（2026-07-20）

- ✅ 内容盘点与挖掘完成（9 域 evidence 映射、三 subagent 深挖、dossier 刷新至 82 sessions）
- ✅ Featured case study：`content/case_study_ch_to_doris.md`
- ✅ **v1 完整站点（本地双语版）**：`site/deep.html`（旧路径 `site/index.html`），双击浏览器打开即用
  - 单文件自包含：L0-L3 三层钻取 + SVG 雷达 + 5 篇 L3 文章 + 8 条 field notes，明暗双主题
  - **中英双语**：`#/en` 与 `#/cn` 两条路径，右上角切换，首次按浏览器语言自动选，选择记入 localStorage；部署为真实站点时对应 `/en` `/cn` 路由
  - 已通过：脱敏 grep 扫描（客户名/PII/内部标识零命中，中英文均查）+ Playwright 双语三层渲染验证
  - 曾发过一版 Claude Artifact 预览，已按用户要求清空下线（彻底删除可在 claude.ai/code/artifacts 操作）
- ✅ **v2 全量纵深版（2026-07-20，6 subagent 并行产出，待用户 review）**
  - 新增 10 篇双语长文：5 项目深页（VM 平台/K8s 升级/流量切换/引擎路由/弹性计算，Why/How/难点骨架）+ 4 视角页（SRE 能力观/当前匹配/接下来/AI agent）+ 1 新事故文（僵尸表 OOM）
  - Case study 开场按 interview story 重构（弃 migration 定性，AI 负载钩子）；dossier 电梯陈述同步重写
  - Oncall 统计集成：7 域 Track Record 行 + 事件响应域 7 失败域索引表 + 8 条新 evidence + 简历 bullet 深挖链接 + 视角页首页入口
  - 构建管道：`build_content.py`（content/*.md → site 模板注入，幂等），md 是 source of truth
- ✅ **口径统一（2026-07-20）**：集群数全站 + resume.tex 统一为 50；40 tenants 移除
- ✅ **告警治理深页 + Jenkins（事实挖掘 + 认知深页）加入**：
  - `content/projects/p_alert_gov.md`（可观测/影响力域，熵增分析章，baseline 数字齐，按门禁目标口径写不声称已达成）
  - `content/projects/p_jenkins.md`（发布/平台域，标题=「SRE 熟悉 Jenkins 到底是什么能力」，幂等/可监控/配置即代码三判据 + 自动化熵增反论 + diagnose→fix→verify mermaid）
  - 新增 CI/CD & Delivery 简历小节；Jenkins evidence 进 platform（含个人 dashboard 工具）+ release 域；alert gov evidence 进 obs + influence
  - 共 12 篇长文、21 case 卡片、6 张 mermaid，脱敏 grep 零命中（含 AKIA/客户名/内部域名）
- 🔴 **需用户处理（非站点，工作 repo 安全）**：`work-harness/code_repos/infra/jenkins-config/jenkins.yaml` L28-31 有明文 AWS AccessKey/SecretKey（AKIAJQXAV6... 起）已进 git 历史 → 轮换密钥 + git 历史清除 + 排查是否活跃。该 repo 分支/环境文件含真实客户名（sony/paypal），永不可公开。
- ⬜ 正式部署：独立 public repo + 自定义域名；nginx P100 after 数据；安全合规域素材（pending）

## 纪律

发布前过 `content_plan.md` 的脱敏规则；每个数字要能指到 evidence 文件；开源措辞用 fork 口径。
