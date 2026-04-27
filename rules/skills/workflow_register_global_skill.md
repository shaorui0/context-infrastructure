# Skill: 注册 Skill 到 Claude Code 全局

## When to Use

用户要求将 context-infrastructure 中的某个 skill 注册为 Claude Code 全局可用（任意目录、任意 session 都能 `/skill-name` 调用）。

触发词："注册到全局"、"全局 skill"、"register skill"、"任何目录都能用"

## Prerequisites

- Skill 源目录在 `context-infrastructure` 中（通常在 `archives/skills/` 或 `rules/skills/` 下）
- 目标：`~/.claude/skills/`（Claude Code 全局 skill 发现目录）

## 核心要求

Claude Code 发现 skill 的条件：
1. `~/.claude/skills/<skill-name>/` 目录存在
2. 目录内有 **`SKILL.md`** 文件（不是 README.md）
3. `SKILL.md` 必须有 YAML frontmatter，包含 `name` 和 `description` 字段

## 流程

### Step 1: 确认源目录

确认 skill 源目录路径和内容：
```bash
ls <source-skill-dir>/
```

### Step 2: 检查是否有 SKILL.md

如果只有 README.md 没有 SKILL.md，需要创建 SKILL.md：

```yaml
---
name: <skill-name>  # 小写 + 连字符
description: <一句话说明 skill 做什么 + 触发条件。这是 Claude Code 决定何时加载此 skill 的唯一依据>
---
```

body 部分从 README.md 迁移核心内容，遵循以下原则：
- 保留操作步骤和关键参数
- 删除"When to Use"段落（已在 description 中）
- 删除"元数据"/"创建日期"等非必要信息
- 保持 < 500 行

### Step 3: 创建 Symlink

```bash
# 如果已有同名空目录，先删除
rmdir ~/.claude/skills/<skill-name> 2>/dev/null

# 创建 symlink
ln -s /Users/rshao/work/context-infrastructure/<relative-path-to-skill> ~/.claude/skills/<skill-name>
```

### Step 4: 验证

```bash
# 1. Symlink 指向正确
ls -la ~/.claude/skills/<skill-name>

# 2. SKILL.md 可读且 frontmatter 正确
head -5 ~/.claude/skills/<skill-name>/SKILL.md

# 3. Claude Code 能发现（启动新的 claude -p 验证）
claude -p "list all your available slash command skills that contain '<keyword>' in the name. just list them, nothing else."
```

Step 3 的验证必须通过才算完成。

## 注意事项

- 用绝对路径创建 symlink（`/Users/rshao/work/context-infrastructure/...`），不用相对路径
- skill name 用小写字母 + 连字符（如 `anki-japanese-flashcard`），目录名可以用下划线
- 如果 skill 同时在 `rules/skills/INDEX.md` 中注册（项目内可用）且需要全局可用，两处都保留
- 修改 SKILL.md 后无需重启——下次 session 自动生效
