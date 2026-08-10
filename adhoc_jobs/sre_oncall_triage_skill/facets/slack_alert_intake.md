# FACET: Slack Alert 接入

## 目的

从 Slack 链接中获取原始告警消息，作为 triage pipeline 的输入源。替代手动粘贴告警文本。

## 输入格式

Slack 消息链接，格式：
```
https://<workspace>.slack.com/archives/<channel_id>/p<timestamp>
```

示例：
```
https://datavisor.slack.com/archives/CJT8ZPRJL/p1775790979547669
```

## 处理流程

### Step 1：解析链接

使用 `tools/slack_link.py` 解析 URL：

```bash
python3 ./tools/slack_link.py "<slack_url>"
```

输出 JSON，包含 `channel_id`、`message_ts`、`thread_ts`（如果是线程）。

### Step 2：获取消息内容

使用 Slack MCP 工具获取具体消息：

```
mcp__slack__slack_list_messages(
  channel=<channel_id>,
  oldest=<message_ts>,
  latest=<message_ts>,
  inclusive=true,
  limit=1
)
```

如果消息有 thread（`thread_ts` 不为空），同时获取线程回复：

```
mcp__slack__slack_list_messages(
  channel=<channel_id>,
  thread_ts=<thread_ts>,
  limit=50
)
```

### Step 3：提取告警内容

从 Slack 消息中提取告警信号：

1. **纯文本内容**：消息 `text` 字段，通常包含告警标题和描述
2. **附件 (attachments)**：很多告警机器人（Alertmanager, PagerDuty, Grafana）通过 attachments 发送结构化数据
3. **Blocks**：Slack Block Kit 格式的结构化内容
4. **线程回复**：可能包含额外上下文、oncall 讨论、相关链接

#### 告警消息常见结构

| 字段 | 含义 | 提取方式 |
|------|------|---------|
| `text` | 主消息文本 | 直接读取 |
| `attachments[].text` | 附件文本（告警详情） | 遍历 attachments |
| `attachments[].fields` | 结构化字段（severity, cluster 等） | 遍历 fields |
| `attachments[].color` | 告警级别颜色（danger=red, warning=yellow） | 映射到 severity |
| `blocks[].text.text` | Block Kit 文本 | 遍历 blocks |
| `bot_id` / `username` | 发送方（Alertmanager, Grafana 等） | 识别告警来源 |

#### 常见告警来源识别

| bot_id / username 特征 | 来源 | 告警格式 |
|------------------------|------|---------|
| Alertmanager / prometheus | Alertmanager | labels + annotations in attachments |
| Grafana | Grafana Alerting | panel snapshot + values in attachments |
| PagerDuty | PagerDuty | incident details in attachments |
| 自定义 bot | 内部工具 | 需按实际结构解析 |

### Step 4：组装为 triage 输入

将提取的告警内容格式化为标准输入，传入 triage pipeline：

```
## 来源
Slack: <原始链接>
Channel: <channel_name> (<channel_id>)
时间: <message timestamp>

## 原始告警
<提取的告警文本，保留原始格式>

## 附加上下文
<来自线程回复的相关信息，如果有>
```

然后按照 `facets/signal_extraction.md` 的流程提取信号，进入正常的 triage 路径。

## 辅助操作

### 获取 Channel 信息

如果需要知道 channel 名称和用途：

```
mcp__slack__slack_get_channel_info(channel_id=<channel_id>)
```

### 搜索相关消息

如果需要查找同一告警的历史出现：

```
mcp__slack__slack_search_messages(query="<alertname> in:<channel_name>", sort="timestamp", sort_dir="desc")
```

## 注意事项

- Slack MCP 是**只读**操作，不会发送消息或修改任何内容
- 所有 Slack MCP 调用都经过 `mcp-audit.sh` 审计
- 如果消息内容为空或无法解析，标记为 `UNKNOWN` 并要求用户手动粘贴告警文本
- 线程中的讨论内容仅作为参考上下文，不直接作为 triage 信号
