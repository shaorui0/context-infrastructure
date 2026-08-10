import React, { useState, useMemo } from "react";
import {
  Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer,
} from "recharts";

/* ------------------------------------------------------------------ *
 *  DATA — this is the whole resume. Edit this object; the UI follows.
 *  `depth`   = how deep you actually go (0–100). Your true strengths.
 *  `target`  = where you want to be. The gap is honest and on purpose.
 *  `group`   = clusters the axis (colours the shape).
 * ------------------------------------------------------------------ */
const PROFILE = {
  name: "Rui",
  role: "Site Reliability / Data Infrastructure Engineer",
  thesis:
    "I operate the loop between what a system should do and what it actually does — and I keep that loop from rotting.",
  location: "Kobe, Japan",
  years: 10,
};

const GROUPS = {
  foundation: { label: "Foundations · why systems break", tone: "signal" },
  operate:    { label: "Operate · steady state",          tone: "signal" },
  deliver:    { label: "Deliver · safe change",           tone: "signal" },
  frontier:   { label: "Frontier · actively building",    tone: "cool"   },
};

const COMPETENCIES = [
  {
    id: "dist", axis: "Distributed\nSystems", group: "foundation",
    depth: 82, target: 90,
    tagline: "The intellectual core: partial failure, no global truth.",
    skills: ["Consensus / replication", "Idempotency + retry semantics", "Backpressure & cascading failure", "CAP / PACELC trade-offs", "Sharding & leader election"],
    projects: [
      { name: "Doris storage-compute separation cluster", note: "Stood up on K8s/AWS with FoundationDB + S3 vault; reasoned through the Result-Sink bottleneck and Arrow-Flight vs JDBC transport." },
    ],
    thinking: {
      title: "There is no global truth — only stale local views and a network that lies.",
      body: "Distributed systems aren't hard because of transactions. They're hard because of partial failure: a request may have succeeded on the far side while the reply was lost, so you never truly know. Idempotency, retries, timeouts, backpressure — none of these are techniques I reach for; they're forced moves once you accept that 'don't know' as the ground truth.",
    },
  },
  {
    id: "data", axis: "Data &\nState", group: "foundation",
    depth: 80, target: 88,
    tagline: "Where errors stop being reversible.",
    skills: ["Backup / verified restore (RTO·RPO)", "Schema migration (expand-migrate-contract)", "Replica-aware pod lifecycle", "Stateful upgrades & one-way doors", "Cross-region data movement"],
    projects: [
      { name: "Year-long Galileo transaction dump: prod → preprod S3", note: "Full-year partner data extraction from ClickHouse; hit a K8s context mismatch (us-west-2 ↔ us-east-1) and treated the copy as strictly non-destructive until row-count + checksum parity was proven." },
    ],
    thinking: {
      title: "Stateless failures are reversible. Stateful ones are not.",
      body: "A stateless pod dies and you just restart it — it held no truth. A database pod is the truth. So every operation gets treated as a one-way door until I've proven it has a tested path back. 'When can I restart this pod?' is really 'how many healthy replicas hold this data, and will it flush cleanly on the way down?'",
    },
  },
  {
    id: "obs", axis: "Observability", group: "operate",
    depth: 78, target: 85,
    tagline: "The sensor in the control loop — not a wall of dashboards.",
    skills: ["SLI/SLO design", "Alert on symptoms, debug on causes", "Four Golden Signals · RED · USE", "High-cardinality events & tracing", "Alert-noise auditing"],
    projects: [
      { name: "ClickHouse / Doris benchmark observability", note: "Instrumented wide-table vs narrow-table query paths to isolate the Result-Sink bottleneck rather than guessing from resource graphs." },
    ],
    thinking: {
      title: "A metric that can't change a decision is noise.",
      body: "Monitoring's real job is to measure the gap between intent and reality before it becomes user-visible harm. Symptoms (SLOs) get paged on; causes (CPU, saturation) are for debugging. The junior mistake is alerting on causes and then drowning — because a resource metric and user harm are not 1:1.",
    },
  },
  {
    id: "incident", axis: "Incident &\nReliability", group: "operate",
    depth: 62, target: 82,
    tagline: "Where everything meets reality — and where the loop learns.",
    skills: ["On-call & incident command", "Error-budget operation", "Blameless postmortems", "Runbooks", "Chaos & failure injection"],
    projects: [
      { name: "(add an incident you led)", note: "Frame it as: symptom → localisation → reversible fix → what the loop learned. The postmortem matters more than the fix." },
    ],
    thinking: {
      title: "On-call is where the system tells you which part of the loop is broken.",
      body: "It has two jobs, not one. In the moment: stop the bleeding, read symptoms before causes, never operate a stateful thing with a stateless reflex. After: turn the incident into an edit to the loop itself — did monitoring see it first? was it a recurrence? which intent-chain snapped? Fixing only the incident is the junior move.",
    },
  },
  {
    id: "release", axis: "Release &\nChange", group: "deliver",
    depth: 66, target: 78,
    tagline: "Safely applying the biggest source of disturbance: change.",
    skills: ["CI/CD pipelines as an SLI", "Canary / progressive delivery", "Cheap, fast rollback", "Flaky-test root-causing"],
    projects: [{ name: "(add a delivery-safety project)", note: "e.g. cutting rollback time so releases stop requiring courage." }],
    thinking: {
      title: "Make rollback so cheap that nobody fears shipping.",
      body: "A release is the largest disturbance you inject into a running system. Canary slices that disturbance into small doses (feed-forward). The senior lever isn't more gates — it's making the reverse gate so cheap that small, frequent change becomes the organisation's default instead of an act of bravery.",
    },
  },
  {
    id: "platform", axis: "Platform &\nAutomation", group: "deliver",
    depth: 76, target: 85,
    tagline: "Baking the control loop into code so it runs without me.",
    skills: ["Reconciliation / controllers", "Declarative interfaces", "K8s internals (informer, level-triggered)", "Harness / context engineering"],
    projects: [
      { name: "Agent architecture & harness engineering", note: "Explored agent-loop / context-engineering frameworks professionally — the same reconcile-toward-intent pattern, applied to agents." },
    ],
    thinking: {
      title: "A platform doesn't close a diff once. It closes it forever.",
      body: "The difference between a script and a controller is time. A script flattens one diff; a controller reconciles toward the desired state on a loop that never sleeps. K8s is level-triggered, not edge-triggered — it converges to a state, not a reaction to events. That's its soul, and it's the template for every platform worth building.",
    },
  },
  {
    id: "infra", axis: "Infra &\nCapacity", group: "deliver",
    depth: 74, target: 80,
    tagline: "The physical substrate — declared, not hand-tended.",
    skills: ["IaC (declarative desired state)", "Autoscaling loops", "Capacity planning (feed-forward)", "Cost / FinOps awareness"],
    projects: [{ name: "K8s-on-AWS environments", note: "Benchmark & preprod clusters for OLAP infra." }],
    thinking: {
      title: "Don't add resources to fight entropy — lower the cost of order.",
      body: "The junior response to entropy is to add more force: more nodes, more on-call, more workarounds. But much of that added 'force' is itself a new entropy source. The senior move is structural: change the system so the energy it takes to stay ordered goes down.",
    },
  },
  {
    id: "security", axis: "Security &\nCompliance", group: "frontier",
    depth: 34, target: 65,
    tagline: "Deliberately pending — a known gap, named honestly.",
    skills: ["Secrets management", "Least-privilege / IAM", "Supply-chain security", "Compliance auditing"],
    projects: [{ name: "(intentional growth area)", note: "Currently de-prioritised in favour of distributed / data / on-call. Listed because a real gap named beats a fake strength claimed." }],
    thinking: {
      title: "Availability isn't the only implicit contract. 'Not breached' is one too.",
      body: "I'm being explicit that this is a frontier, not a strength. A resume that claims 9-out-of-9 mastery is a red flag to anyone senior. This axis is short on purpose — and I'd rather show you the true shape than a flattering blob.",
    },
  },
  {
    id: "influence", axis: "Influence &\nComms", group: "frontier",
    depth: 48, target: 75,
    tagline: "The senior gate: translating debt into the org's language.",
    skills: ["Cross-team influence", "Translating tech debt into cost", "Technical writing (EN/中/日)", "Driving alignment on intent"],
    projects: [
      { name: "Translating infra findings for an EN-speaking team", note: "Regularly turn Doris/ClickHouse findings into English write-ups — the first rung of the influence ladder." },
    ],
    thinking: {
      title: "Half of senior SRE is fighting entropy; the other half is fighting the org's incentives.",
      body: "Root-cause work pays off as 'nothing happened' — invisible, unrewarded. Workarounds are visible and praised. So the org systematically starves the very energy that keeps the loop from rotting. The hardest, highest-leverage skill is making the invisible debt visible in language the org will fund.",
    },
  },
];

/* ------------------------------------------------------------------ */

const C = {
  paper:  "#ECEDE7",
  panel:  "#F4F4EF",
  ink:    "#1B2A33",
  inkSoft:"#3A4A52",
  muted:  "#6E767B",
  line:   "rgba(27,42,51,0.14)",
  signal: "#B9822B", // aged gauge amber — strengths
  cool:   "#3E7075", // muted petrol — frontier / growth
};

function toneColor(tone) { return tone === "cool" ? C.cool : C.signal; }

export default function App() {
  const [openId, setOpenId] = useState(null);
  const [hoverId, setHoverId] = useState(null);
  const open = COMPETENCIES.find((c) => c.id === openId) || null;

  const radarData = useMemo(
    () => COMPETENCIES.map((c) => ({
      id: c.id, axis: c.axis, depth: c.depth, target: c.target,
    })),
    []
  );

  const activeId = hoverId || openId;

  return (
    <div style={{ background: C.paper, color: C.ink, fontFamily: "'Inter', system-ui, sans-serif", minHeight: "100%" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');
        * { box-sizing: border-box; }
        .disp { font-family: 'Space Grotesk', system-ui, sans-serif; }
        .mono { font-family: 'JetBrains Mono', ui-monospace, monospace; }
        .lift { transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease; }
        .lift:hover { transform: translateY(-2px); }
        .fade { animation: fade .35s ease both; }
        @keyframes fade { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }
        .chip { transition: background .15s ease, color .15s ease; }
        @media (prefers-reduced-motion: reduce) {
          .lift, .fade, .chip { transition: none !important; animation: none !important; }
        }
        .axisLabel { cursor: pointer; }
      `}</style>

      <div style={{ maxWidth: 1120, margin: "0 auto", padding: "clamp(28px,5vw,64px) clamp(20px,4vw,48px)" }}>

        {/* ---- L0: the thesis / recruiter fast-path ---- */}
        <header style={{ borderBottom: `1px solid ${C.line}`, paddingBottom: 34, marginBottom: 40 }}>
          <div className="mono" style={{ fontSize: 12, letterSpacing: ".14em", color: C.muted, marginBottom: 18, display: "flex", gap: 18, flexWrap: "wrap" }}>
            <span>{PROFILE.role.toUpperCase()}</span>
            <span style={{ color: C.line }}>│</span>
            <span>{PROFILE.location.toUpperCase()}</span>
            <span style={{ color: C.line }}>│</span>
            <span>~{PROFILE.years} YRS</span>
          </div>
          <h1 className="disp" style={{ fontSize: "clamp(28px,4.6vw,52px)", lineHeight: 1.08, fontWeight: 600, letterSpacing: "-0.02em", margin: 0, maxWidth: 20 + "ch" === "20ch" ? undefined : undefined }}>
            <span style={{ maxWidth: "18ch", display: "inline-block" }}>{PROFILE.name}.</span>
          </h1>
          <p className="disp" style={{ fontSize: "clamp(19px,2.4vw,27px)", lineHeight: 1.32, fontWeight: 400, color: C.inkSoft, margin: "14px 0 0", maxWidth: "30ch" }}>
            {PROFILE.thesis}
          </p>
          <p style={{ fontSize: 14.5, lineHeight: 1.6, color: C.muted, margin: "20px 0 0", maxWidth: "62ch" }}>
            This is a resume you can zoom into. The shape below is honest — it shows where I go deep
            and where I'm still building. Tap any axis to drop from the map into the skills, the work,
            and the way I actually think about it.
          </p>
        </header>

        {/* ---- L1: the honest radar + reading guide ---- */}
        <section style={{ display: "grid", gridTemplateColumns: "minmax(0,1.15fr) minmax(0,1fr)", gap: "clamp(20px,4vw,48px)", alignItems: "center", marginBottom: 46 }}>
          <div style={{ position: "relative" }}>
            <div className="mono" style={{ fontSize: 11, letterSpacing: ".14em", color: C.muted, marginBottom: 8 }}>
              COMPETENCY MAP · depth vs. target
            </div>
            <div style={{ width: "100%", height: 380 }}>
              <ResponsiveContainer>
                <RadarChart data={radarData} outerRadius="72%" margin={{ top: 22, right: 30, bottom: 22, left: 30 }}>
                  <PolarGrid stroke={C.line} />
                  <PolarAngleAxis
                    dataKey="axis"
                    tick={(props) => <AxisTick {...props} data={radarData} activeId={activeId}
                      onEnter={setHoverId} onLeave={() => setHoverId(null)} onClick={setOpenId} />}
                  />
                  <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
                  <Radar name="target" dataKey="target" stroke={C.muted} strokeDasharray="3 3"
                    strokeWidth={1} fill="none" />
                  <Radar name="depth" dataKey="depth" stroke={C.signal} strokeWidth={2}
                    fill={C.signal} fillOpacity={0.16} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div>
            <ReadRow color={C.signal} solid label="Depth" text="Where I actually go deep — the load-bearing skills." />
            <ReadRow color={C.muted} dashed label="Target" text="Where I want to be. The gap is deliberate, not hidden." />
            <div style={{ borderTop: `1px solid ${C.line}`, margin: "18px 0", }} />
            {Object.entries(GROUPS).map(([k, g]) => (
              <div key={k} style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 9 }}>
                <span style={{ width: 9, height: 9, borderRadius: 2, background: toneColor(g.tone), flexShrink: 0, transform: "translateY(1px)" }} />
                <span style={{ fontSize: 13.5, color: C.inkSoft }}>{g.label}</span>
              </div>
            ))}
            <p style={{ fontSize: 12.5, color: C.muted, lineHeight: 1.55, marginTop: 16 }}>
              Nine axes, not six. A profile that peaks everywhere is a tell; a real one has a shape.
            </p>
          </div>
        </section>

        {/* ---- L2 grid: every competency as a tappable card ---- */}
        <div className="mono" style={{ fontSize: 11, letterSpacing: ".14em", color: C.muted, marginBottom: 14 }}>
          NINE AXES · tap to open
        </div>
        <section style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(248px,1fr))", gap: 14, marginBottom: 60 }}>
          {COMPETENCIES.map((c) => {
            const col = toneColor(GROUPS[c.group].tone);
            return (
              <button key={c.id} onClick={() => setOpenId(c.id)}
                onMouseEnter={() => setHoverId(c.id)} onMouseLeave={() => setHoverId(null)}
                className="lift"
                style={{
                  textAlign: "left", background: C.panel, border: `1px solid ${C.line}`,
                  borderRadius: 10, padding: "16px 16px 15px", cursor: "pointer",
                  boxShadow: activeId === c.id ? `0 6px 20px rgba(27,42,51,.10)` : "none",
                  borderColor: activeId === c.id ? col : C.line,
                }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
                  <span className="disp" style={{ fontSize: 16.5, fontWeight: 600, lineHeight: 1.15 }}>
                    {c.axis.replace("\n", " ")}
                  </span>
                  <span className="mono" style={{ fontSize: 12, color: col, flexShrink: 0 }}>{c.depth}</span>
                </div>
                {/* depth bar */}
                <div style={{ height: 4, background: C.line, borderRadius: 2, margin: "12px 0 11px", position: "relative" }}>
                  <div style={{ position: "absolute", inset: 0, width: `${c.target}%`, borderRight: `1px solid ${C.muted}` }} />
                  <div style={{ height: "100%", width: `${c.depth}%`, background: col, borderRadius: 2 }} />
                </div>
                <p style={{ fontSize: 12.8, color: C.muted, lineHeight: 1.5, margin: 0 }}>{c.tagline}</p>
              </button>
            );
          })}
        </section>

        <footer style={{ borderTop: `1px solid ${C.line}`, paddingTop: 22, display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
          <span className="mono" style={{ fontSize: 11.5, color: C.muted, letterSpacing: ".08em" }}>
            A living resume · edit the data, the shape follows
          </span>
          <span className="mono" style={{ fontSize: 11.5, color: C.muted, letterSpacing: ".08em" }}>
            {PROFILE.name.toUpperCase()} · {PROFILE.location.toUpperCase()}
          </span>
        </footer>
      </div>

      {/* ---- L3: drill-down panel ---- */}
      {open && <Detail c={open} onClose={() => setOpenId(null)} />}
    </div>
  );
}

/* custom axis label so it's tappable + reflects active state */
function AxisTick({ x, y, cx, cy, payload, data, activeId, onEnter, onLeave, onClick }) {
  const row = data.find((d) => d.axis === payload.value);
  const isActive = row && row.id === activeId;
  const comp = COMPETENCIES.find((c) => c.id === (row && row.id));
  const col = comp ? toneColor(GROUPS[comp.group].tone) : C.muted;
  const lines = String(payload.value).split("\n");
  const anchor = x > cx + 6 ? "start" : x < cx - 6 ? "end" : "middle";
  return (
    <g className="axisLabel" onClick={() => row && onClick(row.id)}
       onMouseEnter={() => row && onEnter(row.id)} onMouseLeave={onLeave}>
      <text x={x} y={y} textAnchor={anchor} fill={isActive ? col : C.inkSoft}
        fontSize={12} fontWeight={isActive ? 700 : 500}
        fontFamily="'Space Grotesk', sans-serif">
        {lines.map((ln, i) => (
          <tspan key={i} x={x} dy={i === 0 ? -(lines.length - 1) * 6 : 13}>{ln}</tspan>
        ))}
      </text>
    </g>
  );
}

function ReadRow({ color, label, text, solid, dashed }) {
  return (
    <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 11 }}>
      <svg width="26" height="10" style={{ flexShrink: 0, transform: "translateY(2px)" }}>
        <line x1="0" y1="5" x2="26" y2="5" stroke={color} strokeWidth={solid ? 2.5 : 1.5}
          strokeDasharray={dashed ? "3 3" : "0"} />
      </svg>
      <span style={{ fontSize: 13.5 }}>
        <b style={{ fontWeight: 600 }}>{label}.</b> <span style={{ color: C.muted }}>{text}</span>
      </span>
    </div>
  );
}

function Detail({ c, onClose }) {
  const col = toneColor(GROUPS[c.group].tone);
  return (
    <div onClick={onClose}
      style={{ position: "fixed", inset: 0, background: "rgba(27,42,51,.42)", zIndex: 50,
        display: "flex", justifyContent: "flex-end" }}>
      <div className="fade" onClick={(e) => e.stopPropagation()}
        style={{ width: "min(560px, 94vw)", height: "100%", background: C.paper,
          borderLeft: `3px solid ${col}`, overflowY: "auto", padding: "clamp(24px,4vw,42px)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div className="mono" style={{ fontSize: 11, letterSpacing: ".14em", color: col }}>
            {GROUPS[c.group].label.toUpperCase()}
          </div>
          <button onClick={onClose} aria-label="Close"
            style={{ border: "none", background: "none", cursor: "pointer", fontSize: 22, color: C.muted, lineHeight: 1 }}>×</button>
        </div>

        <h2 className="disp" style={{ fontSize: 30, fontWeight: 600, letterSpacing: "-0.01em", margin: "10px 0 4px", lineHeight: 1.1 }}>
          {c.axis.replace("\n", " ")}
        </h2>
        <div className="mono" style={{ fontSize: 12.5, color: C.muted }}>
          depth {c.depth} · target {c.target}
        </div>
        <p style={{ fontSize: 15, color: C.inkSoft, lineHeight: 1.55, margin: "14px 0 0" }}>{c.tagline}</p>

        {/* thinking — the differentiator, on top */}
        <div style={{ background: C.panel, border: `1px solid ${C.line}`, borderRadius: 12, padding: "18px 20px", margin: "26px 0" }}>
          <div className="mono" style={{ fontSize: 10.5, letterSpacing: ".16em", color: col, marginBottom: 9 }}>HOW I THINK ABOUT IT</div>
          <p className="disp" style={{ fontSize: 17.5, fontWeight: 500, lineHeight: 1.34, margin: "0 0 10px" }}>{c.thinking.title}</p>
          <p style={{ fontSize: 14, lineHeight: 1.62, color: C.inkSoft, margin: 0 }}>{c.thinking.body}</p>
        </div>

        <Section label="SKILLS & TECH">
          <div style={{ display: "flex", flexWrap: "wrap", gap: 7 }}>
            {c.skills.map((s) => (
              <span key={s} className="mono" style={{ fontSize: 12, padding: "5px 10px", background: C.panel, border: `1px solid ${C.line}`, borderRadius: 6, color: C.inkSoft }}>{s}</span>
            ))}
          </div>
        </Section>

        <Section label="SELECTED WORK">
          {c.projects.map((p, i) => (
            <div key={i} style={{ marginBottom: 14 }}>
              <div className="disp" style={{ fontSize: 14.5, fontWeight: 600, marginBottom: 3 }}>{p.name}</div>
              <p style={{ fontSize: 13.5, lineHeight: 1.55, color: C.muted, margin: 0 }}>{p.note}</p>
            </div>
          ))}
        </Section>
      </div>
    </div>
  );
}

function Section({ label, children }) {
  return (
    <div style={{ marginBottom: 24 }}>
      <div className="mono" style={{ fontSize: 10.5, letterSpacing: ".16em", color: C.muted, marginBottom: 11, borderBottom: `1px solid ${C.line}`, paddingBottom: 7 }}>{label}</div>
      {children}
    </div>
  );
}
