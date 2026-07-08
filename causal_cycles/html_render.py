"""Render a DiGraph as a self-contained, interactive HTML page.

No external dependencies (no graphviz, no CDN JS): node positions are
computed client-side with a small vanilla-JS force-directed layout, and the
whole thing - data, CSS, JS - lives in one HTML file you can open directly
in a browser.
"""
from __future__ import annotations

import json

from causal_cycles.graph import DiGraph

_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>{title} · influence graph</title>
<style>
:root {{
  --bg: #f6f8fb;
  --panel: #ffffff;
  --border: #dde3ec;
  --text: #1b2433;
  --text-dim: #5c6a80;
  --accent: #0e8fa0;
  --accent-soft: #0e8fa01a;
  --critical: #c9432f;
  --critical-soft: #c9432f1a;
}}
@media (prefers-color-scheme: dark) {{
  :root {{
    --bg: #10141c;
    --panel: #171d29;
    --border: #2a3244;
    --text: #e7ecf5;
    --text-dim: #8793a8;
    --accent: #5fd3e0;
    --accent-soft: #5fd3e026;
    --critical: #ff7a68;
    --critical-soft: #ff7a6826;
  }}
}}
:root[data-theme="dark"] {{
  --bg: #10141c;
  --panel: #171d29;
  --border: #2a3244;
  --text: #e7ecf5;
  --text-dim: #8793a8;
  --accent: #5fd3e0;
  --accent-soft: #5fd3e026;
  --critical: #ff7a68;
  --critical-soft: #ff7a6826;
}}
:root[data-theme="light"] {{
  --bg: #f6f8fb;
  --panel: #ffffff;
  --border: #dde3ec;
  --text: #1b2433;
  --text-dim: #5c6a80;
  --accent: #0e8fa0;
  --accent-soft: #0e8fa01a;
  --critical: #c9432f;
  --critical-soft: #c9432f1a;
}}

* {{ box-sizing: border-box; }}
html, body {{
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: ui-sans-serif, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
}}
body {{
  padding: 2.5rem clamp(1rem, 4vw, 3rem) 3rem;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}}
.mono {{
  font-family: ui-monospace, "SF Mono", "Cascadia Code", "JetBrains Mono", Menlo, Consolas, monospace;
}}

header {{
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  justify-content: space-between;
  gap: 1rem 2rem;
  border-bottom: 1px solid var(--border);
  padding-bottom: 1.25rem;
}}
header .titles h1 {{
  margin: 0;
  font-size: 1.5rem;
  font-weight: 700;
  letter-spacing: -0.01em;
  text-wrap: balance;
}}
header .titles p {{
  margin: 0.3rem 0 0;
  color: var(--text-dim);
  font-size: 0.9rem;
}}
.stats {{
  display: flex;
  gap: 0.6rem;
}}
.stat {{
  border: 1px solid var(--border);
  background: var(--panel);
  border-radius: 8px;
  padding: 0.5rem 0.85rem;
  min-width: 5.5rem;
  text-align: center;
}}
.stat .n {{
  display: block;
  font-size: 1.25rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}}
.stat .l {{
  display: block;
  font-size: 0.65rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-dim);
  margin-top: 0.15rem;
}}
.stat.critical .n {{ color: var(--critical); }}

.panel {{
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 12px;
}}
.canvas-panel {{
  padding: 0.5rem;
  overflow: auto;
}}
svg {{ display: block; width: 100%; height: auto; }}

.node circle {{
  fill: var(--panel);
  stroke: var(--accent);
  stroke-width: 2;
}}
.node.cyclic circle {{
  fill: var(--critical-soft);
  stroke: var(--critical);
}}
.node text {{
  fill: var(--text);
  font-size: 12px;
  text-anchor: middle;
  pointer-events: none;
}}
.node {{ cursor: grab; }}
.node:active {{ cursor: grabbing; }}

.edge path {{
  fill: none;
  stroke: var(--text-dim);
  stroke-width: 1.4;
  opacity: 0.7;
  marker-end: url(#arrow);
}}
.edge.cyclic path {{
  stroke: var(--critical);
  stroke-width: 2;
  opacity: 0.95;
  marker-end: url(#arrow-critical);
}}

.legend {{
  display: flex;
  flex-wrap: wrap;
  gap: 1.1rem;
  padding: 0.85rem 1rem;
  color: var(--text-dim);
  font-size: 0.78rem;
  border-top: 1px solid var(--border);
}}
.legend span {{ display: inline-flex; align-items: center; gap: 0.4rem; }}
.swatch {{ width: 0.8rem; height: 0.8rem; border-radius: 50%; display: inline-block; }}
.swatch.var {{ background: var(--panel); border: 2px solid var(--accent); }}
.swatch.cyc {{ background: var(--critical-soft); border: 2px solid var(--critical); }}
.line {{ width: 1.1rem; height: 2px; display: inline-block; }}
.line.var {{ background: var(--text-dim); }}
.line.cyc {{ background: var(--critical); }}

.cycles h2 {{
  font-size: 0.95rem;
  margin: 0;
  padding: 0.9rem 1.1rem 0.6rem;
  color: var(--text-dim);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}}
.cycle-list {{
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0 1.1rem 1.1rem;
}}
.cycle-chain {{
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.85rem;
}}
.chip {{
  background: var(--critical-soft);
  color: var(--critical);
  border: 1px solid var(--critical);
  border-radius: 999px;
  padding: 0.12rem 0.6rem;
}}
.arrow {{ color: var(--text-dim); }}
.empty {{
  padding: 1.1rem;
  color: var(--text-dim);
  font-size: 0.85rem;
}}

footer {{
  color: var(--text-dim);
  font-size: 0.78rem;
  text-align: center;
}}
footer code {{
  background: var(--accent-soft);
  border-radius: 4px;
  padding: 0.1rem 0.35rem;
}}
</style>
</head>
<body>

<header>
  <div class="titles">
    <h1 class="mono">{title}</h1>
    <p>numeric-variable influence graph — an edge y&nbsp;&rarr;&nbsp;x means an effect sets x from an expression reading y</p>
  </div>
  <div class="stats">
    <div class="stat"><span class="n">{n_vars}</span><span class="l">variables</span></div>
    <div class="stat"><span class="n">{n_edges}</span><span class="l">edges</span></div>
    <div class="stat{cycle_stat_class}"><span class="n">{n_cycles}</span><span class="l">cycles</span></div>
  </div>
</header>

<div class="panel canvas-panel">
  <svg id="graph" viewBox="0 0 900 560" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M0,0 L10,5 L0,10 z" fill="var(--text-dim)"></path>
      </marker>
      <marker id="arrow-critical" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M0,0 L10,5 L0,10 z" fill="var(--critical)"></path>
      </marker>
    </defs>
    <g id="edges"></g>
    <g id="nodes"></g>
  </svg>
  <div class="legend">
    <span><span class="swatch var"></span>variable</span>
    <span><span class="swatch cyc"></span>variable on a cycle</span>
    <span><span class="line var"></span>influence</span>
    <span><span class="line cyc"></span>influence on a cycle</span>
    <span>drag nodes to rearrange · hover an edge for the action name</span>
  </div>
</div>

<div class="panel cycles">
  <h2>Detected cycles</h2>
  <div class="cycle-list" id="cycle-list"></div>
</div>

<footer>generated by <code>causal_cycles</code> — rerun against another domain with <code>python3 -m causal_cycles.cli &lt;domain.pddl&gt; --html-dir &lt;dir&gt;</code></footer>

<script id="graph-data" type="application/json">{data_json}</script>
<script>
const data = JSON.parse(document.getElementById('graph-data').textContent);
const W = 900, H = 560;

const cycleList = document.getElementById('cycle-list');
if (data.cycles.length === 0) {{
  cycleList.innerHTML = '<div class="empty">No cycles — the influence graph is a DAG.</div>';
  cycleList.classList.remove('cycle-list');
}} else {{
  for (const cyc of data.cycles) {{
    const row = document.createElement('div');
    row.className = 'cycle-chain';
    const chain = cyc.length > 1 ? [...cyc, cyc[0]] : [cyc[0], cyc[0]];
    chain.forEach((n, i) => {{
      const chip = document.createElement('span');
      chip.className = 'chip mono';
      chip.textContent = n;
      row.appendChild(chip);
      if (i < chain.length - 1) {{
        const arrow = document.createElement('span');
        arrow.className = 'arrow';
        arrow.textContent = '\\u2192';
        row.appendChild(arrow);
      }}
    }});
    cycleList.appendChild(row);
  }}
}}

// --- force-directed layout (Fruchterman-Reingold style, run once on load) ---
const nodes = data.nodes.map((n, i) => ({{
  ...n,
  x: W / 2 + Math.cos(i / data.nodes.length * 2 * Math.PI) * (Math.min(W, H) * 0.32),
  y: H / 2 + Math.sin(i / data.nodes.length * 2 * Math.PI) * (Math.min(W, H) * 0.32),
}}));
const byId = Object.fromEntries(nodes.map(n => [n.id, n]));
const links = data.edges.filter(e => e.source !== e.target);

const AREA = W * H;
const K = Math.sqrt(AREA / Math.max(nodes.length, 1)) * 0.9;
let temperature = Math.max(W, H) * 0.05;

for (let iter = 0; iter < 300; iter++) {{
  const disp = new Map(nodes.map(n => [n.id, {{x: 0, y: 0}}]));

  for (let i = 0; i < nodes.length; i++) {{
    for (let j = i + 1; j < nodes.length; j++) {{
      const a = nodes[i], b = nodes[j];
      let dx = a.x - b.x, dy = a.y - b.y;
      let dist = Math.hypot(dx, dy) || 0.01;
      const force = (K * K) / dist;
      dx = (dx / dist) * force;
      dy = (dy / dist) * force;
      disp.get(a.id).x += dx; disp.get(a.id).y += dy;
      disp.get(b.id).x -= dx; disp.get(b.id).y -= dy;
    }}
  }}

  for (const e of links) {{
    const a = byId[e.source], b = byId[e.target];
    let dx = a.x - b.x, dy = a.y - b.y;
    let dist = Math.hypot(dx, dy) || 0.01;
    const force = (dist * dist) / K;
    dx = (dx / dist) * force;
    dy = (dy / dist) * force;
    disp.get(a.id).x -= dx; disp.get(a.id).y -= dy;
    disp.get(b.id).x += dx; disp.get(b.id).y += dy;
  }}

  for (const n of nodes) {{
    const d = disp.get(n.id);
    const dist = Math.hypot(d.x, d.y) || 0.01;
    const capped = Math.min(dist, temperature);
    n.x += (d.x / dist) * capped;
    n.y += (d.y / dist) * capped;
    n.x = Math.min(W - 40, Math.max(40, n.x));
    n.y = Math.min(H - 40, Math.max(40, n.y));
  }}
  temperature *= 0.97;
}}

// --- render ---
const svgNS = 'http://www.w3.org/2000/svg';
const nodesG = document.getElementById('nodes');
const edgesG = document.getElementById('edges');
const R = 22;

function el(tag, attrs) {{
  const e = document.createElementNS(svgNS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  return e;
}}

function selfLoopPath(n) {{
  const x = n.x, y = n.y;
  return `M ${{x - R * 0.7}} ${{y - R * 0.7}} C ${{x - R * 2.4}} ${{y - R * 2.6}}, ${{x + R * 0.9}} ${{y - R * 2.6}}, ${{x + R * 0.6}} ${{y - R * 0.75}}`;
}}

function edgePath(a, b) {{
  const dx = b.x - a.x, dy = b.y - a.y;
  const dist = Math.hypot(dx, dy) || 0.01;
  const ux = dx / dist, uy = dy / dist;
  const x1 = a.x + ux * R, y1 = a.y + uy * R;
  const x2 = b.x - ux * R, y2 = b.y - uy * R;
  const mx = (x1 + x2) / 2 - uy * dist * 0.08;
  const my = (y1 + y2) / 2 + ux * dist * 0.08;
  return `M ${{x1}} ${{y1}} Q ${{mx}} ${{my}}, ${{x2}} ${{y2}}`;
}}

const edgeEls = data.edges.map(e => {{
  const g = el('g', {{ class: 'edge' + (e.cyclic ? ' cyclic' : '') }});
  const path = el('path', {{ d: '' }});
  const title = document.createElementNS(svgNS, 'title');
  title.textContent = e.source + ' \\u2192 ' + e.target + (e.labels.length ? ' via ' + e.labels.join(', ') : '');
  g.appendChild(path);
  g.appendChild(title);
  edgesG.appendChild(g);
  return {{ e, path }};
}});

const nodeEls = nodes.map(n => {{
  const g = el('g', {{ class: 'node' + (n.cyclic ? ' cyclic' : ''), transform: `translate(${{n.x}},${{n.y}})` }});
  g.appendChild(el('circle', {{ r: R }}));
  const text = el('text', {{ dy: '0.32em' }});
  text.textContent = n.id;
  g.appendChild(text);
  nodesG.appendChild(g);
  return {{ n, g }};
}});

function reflow() {{
  for (const {{ e, path }} of edgeEls) {{
    if (e.source === e.target) {{
      path.setAttribute('d', selfLoopPath(byId[e.source]));
    }} else {{
      path.setAttribute('d', edgePath(byId[e.source], byId[e.target]));
    }}
  }}
  for (const {{ n, g }} of nodeEls) {{
    g.setAttribute('transform', `translate(${{n.x}},${{n.y}})`);
  }}
}}
reflow();

// --- drag to rearrange ---
const svg = document.getElementById('graph');
let dragging = null;

function svgPoint(evt) {{
  const pt = svg.createSVGPoint();
  pt.x = evt.clientX; pt.y = evt.clientY;
  return pt.matrixTransform(svg.getScreenCTM().inverse());
}}

nodeEls.forEach(({{ n, g }}) => {{
  g.addEventListener('pointerdown', (evt) => {{
    dragging = n;
    g.setPointerCapture(evt.pointerId);
  }});
}});
svg.addEventListener('pointermove', (evt) => {{
  if (!dragging) return;
  const p = svgPoint(evt);
  dragging.x = Math.min(W - 40, Math.max(40, p.x));
  dragging.y = Math.min(H - 40, Math.max(40, p.y));
  reflow();
}});
svg.addEventListener('pointerup', () => dragging = null);
svg.addEventListener('pointerleave', () => dragging = null);
</script>
</body>
</html>
"""


def render_html(graph: DiGraph, title: str) -> str:
    cyclic_nodes = graph.cyclic_nodes()
    cyclic_edges = graph.cyclic_edges()

    node_objs = [{"id": n, "cyclic": n in cyclic_nodes} for n in sorted(graph.nodes)]
    edge_objs = [
        {"source": s, "target": t, "labels": sorted(labels), "cyclic": (s, t) in cyclic_edges}
        for (s, t), labels in sorted(graph.edges.items())
    ]
    cycles = sorted(graph.cycles(), key=lambda c: (-len(c), c))

    data_json = json.dumps({"nodes": node_objs, "edges": edge_objs, "cycles": cycles})

    return _TEMPLATE.format(
        title=title,
        n_vars=len(graph.nodes),
        n_edges=len(graph.edges),
        n_cycles=len(cycles),
        cycle_stat_class=" critical" if cycles else "",
        data_json=data_json,
    )
