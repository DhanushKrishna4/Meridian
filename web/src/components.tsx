import { useEffect, useId, useRef, useState } from "react";
import type { Graph, Moments } from "./types";
import "./visualizations.css";

export function Icon({ name, size = 18 }: { name: string; size?: number }) {
  const paths: Record<string, React.ReactNode> = {
    arrow: (
      <>
        <path d="M4 12h16m-6-6 6 6-6 6" />
      </>
    ),
    play: <path d="m8 5 11 7-11 7V5Z" />,
    spark: (
      <>
        <path d="m12 3 2.2 6.8L21 12l-6.8 2.2L12 21l-2.2-6.8L3 12l6.8-2.2L12 3Z" />
      </>
    ),
    upload: (
      <>
        <path d="M12 16V3m-5 5 5-5 5 5M4 15v5h16v-5" />
      </>
    ),
    download: (
      <>
        <path d="M12 3v13m-5-5 5 5 5-5M4 16v5h16v-5" />
      </>
    ),
    chevron: <path d="m8 5 7 7-7 7" />,
    close: <path d="m6 6 12 12M6 18 18 6" />,
    check: <path d="m5 12 4 4L19 6" />,
    reset: (
      <>
        <path d="M3 10a9 9 0 1 1 2 8M3 4v6h6" />
      </>
    ),
    info: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 11v6m0-10v1" />
      </>
    ),
    table: (
      <>
        <rect x="3" y="4" width="18" height="16" rx="2" />
        <path d="M3 9h18M3 14h18M9 4v16" />
      </>
    ),
    graph: (
      <>
        <circle cx="5" cy="6" r="2" />
        <circle cx="19" cy="7" r="2" />
        <circle cx="12" cy="19" r="2" />
        <path d="m7 6 10 1M6 8l5 9m7-8-5 8" />
      </>
    ),
    eye: (
      <>
        <path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z" />
        <circle cx="12" cy="12" r="3" />
      </>
    ),
    flask: (
      <>
        <path d="M9 3h6m-5 0v7L4 19a1 1 0 0 0 1 2h14a1 1 0 0 0 1-2l-6-9V3M7 16h10" />
      </>
    ),
    lock: (
      <>
        <rect x="5" y="10" width="14" height="11" rx="2" />
        <path d="M8 10V6a4 4 0 0 1 8 0v4" />
      </>
    ),
    layers: (
      <>
        <path d="m12 3 10 5-10 5L2 8l10-5Zm-10 9 10 5 10-5M2 16l10 5 10-5" />
      </>
    ),
    sliders: (
      <>
        <path d="M4 3v18M12 3v18M20 3v18M1 8h6m2 8h6m2-11h6" />
      </>
    ),
    book: (
      <>
        <path d="M12 6C9 3 5 3 2 4v15c4-1 7-1 10 2 3-3 6-3 10-2V4c-3-1-7-1-10 2Zm0 0v15" />
      </>
    ),
    stop: <rect x="6" y="6" width="12" height="12" rx="1" />,
    code: (
      <>
        <path d="m8 6-6 6 6 6m8-12 6 6-6 6m-3-15-2 18" />
      </>
    ),
  };
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name] || paths.info}
    </svg>
  );
}

export function Mark() {
  return (
    <svg
      className="brand-mark"
      viewBox="0 0 42 42"
      fill="none"
      aria-hidden="true"
    >
      <circle cx="21" cy="21" r="16" />
      <ellipse cx="21" cy="21" rx="7" ry="20" />
      <path d="M1 21h40M21 1v40" />
      <circle cx="21" cy="21" r="3" fill="currentColor" />
    </svg>
  );
}
export const fmt = (n: unknown, digits = 3) =>
  typeof n === "number"
    ? Number.isFinite(n)
      ? Math.abs(n) > 9999
        ? n.toExponential(2)
        : n.toLocaleString("en-US", { maximumFractionDigits: digits })
      : "—"
    : "—";
export const pretty = (value: unknown) => JSON.stringify(value, null, 2);
export const label = (value: string) => value.replaceAll("_", " ");

type GraphPoint = { x: number; y: number };

function useElementWidth<T extends Element>(initialWidth: number) {
  const ref = useRef<T>(null),
    [width, setWidth] = useState(initialWidth);
  useEffect(() => {
    if (!ref.current) return;
    const observer = new ResizeObserver((entries) => {
      const next = Math.round(entries[0].contentRect.width);
      if (next > 0) setWidth(next);
    });
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);
  return [ref, width] as const;
}

/** Shared graph renderer: unresolved relationships stay unresolved in every view. */
export function CausalGraph({
  graph,
  selected,
  onSelect,
  mini = false,
  conflicts = [],
  interventions = [],
}: {
  graph: Graph;
  selected?: string;
  onSelect?: (kind: "node" | "edge", id: string) => void;
  mini?: boolean;
  conflicts?: unknown[];
  interventions?: string[];
}) {
  const markerId = `arrow-${useId().replaceAll(":", "")}`;
  const svgRef = useRef<SVGSVGElement>(null),
    [compact, setCompact] = useState(false);
  useEffect(() => {
    if (mini || !svgRef.current) return;
    const observer = new ResizeObserver((entries) =>
      setCompact(entries[0].contentRect.width < 580),
    );
    observer.observe(svgRef.current);
    return () => observer.disconnect();
  }, [mini]);
  const n = graph.nodes.length,
    width = mini ? 340 : compact ? 420 : 850,
    height = mini ? 170 : 380;
  const half = mini
    ? n > 14
      ? 8
      : n > 12
        ? 9
        : n > 11
          ? 10
          : n > 7
            ? 12
            : n === 7
              ? 18
              : 23
    : compact
      ? n > 9
        ? 20
        : n > 5
          ? 26
          : 31
      : n > 9
        ? 22
        : n > 5
          ? 33
          : 43;
  const interactive = !!onSelect && !mini;
  const points: Record<string, GraphPoint> = Object.fromEntries(
    graph.nodes.map((node, i) => {
      if (n === 1) return [node, { x: width / 2, y: height / 2 }];
      if (n === 2)
        return [node, { x: width * (i === 0 ? 0.28 : 0.72), y: height * 0.48 }];
      if (n === 3)
        return [
          node,
          mini
            ? [
                { x: 52, y: 110 },
                { x: 170, y: 48 },
                { x: 288, y: 110 },
              ][i]
            : compact
              ? [
                  { x: 68, y: 250 },
                  { x: 210, y: 95 },
                  { x: 352, y: 250 },
                ][i]
              : [
                  { x: 160, y: 238 },
                  { x: 425, y: 112 },
                  { x: 690, y: 238 },
                ][i],
        ];
      const angle = -Math.PI / 2 + (i * 2 * Math.PI) / n;
      return [
        node,
        {
          x: width / 2 + (mini ? 139 : compact ? 164 : 346) * Math.cos(angle),
          y: height * 0.46 + (mini ? 49 : 120) * Math.sin(angle),
        },
      ];
    }),
  );
  const edges = [
    ...(graph.directed || []).map((e) => ({ e, directed: true })),
    ...(graph.undirected || []).map((e) => ({ e, directed: false })),
  ];
  const graphDescription = `Causal graph: ${n} variables, ${graph.directed?.length || 0} directed and ${graph.undirected?.length || 0} unresolved edges${mini ? `. Variables: ${graph.nodes.join(", ")}. ${edges.map(({ e: [a, b], directed }) => `${a} ${directed ? "directed to" : "unresolved with"} ${b}`).join("; ")}` : ""}`;
  const activate = (
    event: React.KeyboardEvent,
    kind: "node" | "edge",
    id: string,
  ) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onSelect?.(kind, id);
    }
  };
  return (
    <svg
      ref={svgRef}
      viewBox={`0 0 ${width} ${height}`}
      className={`causal-graph viz-graph ${mini ? "mini-graph viz-graph-mini" : ""}`}
      role={interactive ? "group" : "img"}
      aria-label={graphDescription}
    >
      <defs>
        <marker
          id={markerId}
          viewBox="0 0 12 12"
          refX="10"
          refY="6"
          markerWidth="8"
          markerHeight="8"
          orient="auto-start-reverse"
        >
          <path
            d="M2 2 L10 6 L2 10"
            fill="none"
            stroke="context-stroke"
            strokeWidth="1.7"
            strokeLinejoin="round"
          />
        </marker>
      </defs>
      {edges.map(({ e: [a, b], directed }) => {
        const p = points[a],
          q = points[b];
        if (!p || !q) return null;
        const dx = q.x - p.x,
          dy = q.y - p.y,
          length = Math.hypot(dx, dy);
        if (!length) return null;
        const ux = dx / length,
          uy = dy / length,
          boxDistance = half / Math.max(Math.abs(ux), Math.abs(uy));
        const start = boxDistance + 3,
          end = boxDistance + (directed ? 8 : 3),
          id = `${a}|${b}`;
        const active = selected === id || selected === `${b}|${a}`;
        const conflict = conflicts.some(
          (c) =>
            JSON.stringify(c).includes(`"${a}"`) &&
            JSON.stringify(c).includes(`"${b}"`),
        );
        const x1 = p.x + ux * start,
          y1 = p.y + uy * start,
          x2 = q.x - ux * end,
          y2 = q.y - uy * end;
        const description = `${a} ${directed ? "directed to" : "unresolved with"} ${b}${conflict ? ", orientation conflict" : ""}`;
        return (
          <g
            key={id}
            className={`graph-edge viz-edge ${directed ? "directed" : "unresolved"} ${active ? "selected" : ""} ${conflict ? "conflicting" : ""}`}
            onClick={interactive ? () => onSelect("edge", id) : undefined}
            onKeyDown={interactive ? (e) => activate(e, "edge", id) : undefined}
            tabIndex={interactive ? 0 : undefined}
            role={interactive ? "button" : undefined}
            aria-label={description}
          >
            <title>{description}</title>
            <line
              className="edge-hit viz-edge-hit"
              x1={x1}
              y1={y1}
              x2={x2}
              y2={y2}
            />
            <line
              className="edge-line viz-edge-line"
              x1={x1}
              y1={y1}
              x2={x2}
              y2={y2}
              markerEnd={directed ? `url(#${markerId})` : undefined}
            />
            {!mini && n <= 6 && (!compact || conflict) && (
              <text
                className="edge-label viz-edge-label"
                x={(p.x + q.x) / 2 - uy * 14}
                y={(p.y + q.y) / 2 + ux * 14}
                textAnchor="middle"
              >
                {conflict ? "CONFLICT" : directed ? "" : "UNRESOLVED"}
              </text>
            )}
          </g>
        );
      })}
      {graph.nodes.map((node, i) => {
        const p = points[node],
          isIntervened = interventions.includes(node);
        const minimumFont = mini ? (n > 7 ? 9 : 16) : 14,
          innerWidth = half * 2 - (mini ? (n > 7 ? 3 : 9) : 14);
        const maxCharacters = Math.max(
          2,
          Math.floor(innerWidth / (minimumFont * 0.6)),
        );
        const display =
          node.length > maxCharacters
            ? `${node.slice(0, maxCharacters - 1)}…`
            : node;
        const fontSize = Math.max(
          minimumFont,
          Math.min(mini ? 26 : 40, innerWidth / (display.length * 0.6)),
        );
        return (
          <g
            key={node}
            className={`graph-node viz-node ${selected === node ? "selected" : ""} ${isIntervened ? "intervened" : ""}`}
            transform={`translate(${p.x},${p.y})`}
            onClick={interactive ? () => onSelect("node", node) : undefined}
            onKeyDown={
              interactive ? (e) => activate(e, "node", node) : undefined
            }
            tabIndex={interactive ? 0 : undefined}
            role={interactive ? "button" : undefined}
            aria-label={`${interactive ? "Inspect variable" : "Variable"} ${node}${isIntervened ? ", intervened" : ""}`}
          >
            <title>
              {node}
              {isIntervened ? " — intervention replaces this equation" : ""}
            </title>
            <rect
              className="viz-node-focus"
              x={-half - 5}
              y={-half - 5}
              width={half * 2 + 10}
              height={half * 2 + 10}
              rx={mini ? 9 : 14}
            />
            <rect
              className="node-disc viz-node-disc"
              x={-half}
              y={-half}
              width={half * 2}
              height={half * 2}
              rx={mini ? 5 : 9}
            />
            <text
              className="node-name viz-node-name"
              textAnchor="middle"
              dominantBaseline="central"
              style={{ fontSize }}
            >
              {display}
            </text>
            {!mini && n <= 6 && (
              <text
                className="node-number viz-node-index"
                textAnchor="middle"
                y={half + 25}
                style={{ fontSize: compact ? 15 : 13 }}
              >
                {isIntervened
                  ? "INTERVENED"
                  : `VARIABLE ${String(i + 1).padStart(2, "0")}`}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

const axisNumber = (value: number, step?: number) => {
  if (!Number.isFinite(value)) return "—";
  const digits =
    step && step > 0
      ? Math.min(8, Math.max(0, 1 - Math.floor(Math.log10(step))))
      : 2;
  if (value !== 0 && (Math.abs(value) < 0.01 || Math.abs(value) >= 10000))
    return value.toExponential(2);
  return fmt(value, digits);
};

export function Histogram({
  values,
  variable,
}: {
  values: number[];
  variable: string;
}) {
  const [chartRef, chartWidth] = useElementWidth<HTMLDivElement>(300);
  const observations = values.filter(Number.isFinite);
  if (!observations.length)
    return (
      <div ref={chartRef} className="empty-small">
        Select a dataset to inspect its distribution.
      </div>
    );
  const min = observations.reduce((a, b) => Math.min(a, b)),
    max = observations.reduce((a, b) => Math.max(a, b)),
    constant = min === max;
  const extent = constant ? Math.max(0.5, Math.abs(min) * 0.05) : 0;
  const lo = constant ? min - extent : min,
    hi = constant ? max + extent : max,
    span = hi - lo;
  if (!Number.isFinite(span) || span <= 0)
    return (
      <div ref={chartRef} className="empty-small">
        Preview values exceed the plot’s numerical range. Inspect the
        observations for exact values.
      </div>
    );
  const bins = new Array(20).fill(0);
  observations.forEach(
    (v) =>
      bins[Math.min(19, Math.max(0, Math.floor(((v - lo) / span) * 20)))]++,
  );
  const highest = Math.max(...bins),
    width = Math.max(220, chartWidth),
    left = 32,
    right = width - 8,
    top = 27,
    bottom = 134,
    plotWidth = right - left;
  const y = (count: number) => bottom - (count / highest) * (bottom - top);
  const countTicks = [0, Math.ceil(highest / 2), highest].filter(
    (v, i, a) => a.indexOf(v) === i,
  );
  return (
    <div ref={chartRef} className="histogram viz-histogram">
      <svg
        viewBox={`0 0 ${width} 180`}
        role="img"
        aria-label={`Histogram of ${variable}: ${observations.length} preview observations, minimum ${fmt(min)}, maximum ${fmt(max)}. Bar heights show observation counts.`}
      >
        <text className="viz-axis-title" x={left} y="13">
          COUNT
        </text>
        {countTicks.map((count) => (
          <g key={count}>
            <line
              className="viz-grid"
              x1={left}
              x2={right}
              y1={y(count)}
              y2={y(count)}
            />
            <text
              className="viz-tick"
              textAnchor="end"
              x={left - 8}
              y={y(count) + 4}
            >
              {count}
            </text>
          </g>
        ))}
        {bins.map((count, i) => (
          <rect
            className="viz-histogram-bar"
            key={i}
            x={left + (i * plotWidth) / 20 + 1}
            y={y(count)}
            width={Math.max(1, plotWidth / 20 - 2)}
            height={bottom - y(count)}
            rx=".5"
          >
            <title>
              {axisNumber(lo + (i * span) / 20, span / 20)} to{" "}
              {axisNumber(lo + ((i + 1) * span) / 20, span / 20)}: {count}{" "}
              observations
            </title>
          </rect>
        ))}
        <line
          className="viz-axis"
          x1={left}
          x2={right}
          y1={bottom}
          y2={bottom}
        />
        {[lo, (lo + hi) / 2, hi].map((v, i) => (
          <g key={i}>
            <line
              className="viz-axis"
              x1={left + (i * plotWidth) / 2}
              x2={left + (i * plotWidth) / 2}
              y1={bottom}
              y2={bottom + 5}
            />
            <text
              className="viz-tick"
              x={left + (i * plotWidth) / 2}
              y={bottom + 22}
              textAnchor={i === 0 ? "start" : i === 2 ? "end" : "middle"}
            >
              {axisNumber(v, span / 2)}
            </text>
          </g>
        ))}
        <text className="viz-axis-title" x={right} y="178" textAnchor="end">
          ORIGINAL UNITS
        </text>
      </svg>
      <div className="viz-chart-caption">
        <span>{observations.length.toLocaleString()} preview rows</span>
        <span>
          {constant
            ? "All preview values are identical"
            : "20 equal-width bins"}
        </span>
      </div>
    </div>
  );
}

export function DistributionChart({
  observational,
  interventional,
  index,
}: {
  observational: Moments;
  interventional: Moments;
  index: number;
}) {
  const [chartRef, chartWidth] = useElementWidth<HTMLDivElement>(640);
  const a = observational.mean[index],
    b = interventional.mean[index],
    va = observational.covariance[index]?.[index],
    vb = interventional.covariance[index]?.[index];
  if (![a, b, va, vb].every(Number.isFinite))
    return (
      <div ref={chartRef} className="empty-small">
        A finite mean and variance are required to display this outcome.
      </div>
    );
  const sa = Math.sqrt(Math.max(0, va)),
    sb = Math.sqrt(Math.max(0, vb));
  const distributions = [
    { mean: a, sd: sa, name: "Condition", key: "condition" },
    { mean: b, sd: sb, name: "Intervene", key: "intervene" },
  ];
  const rawLo = Math.min(a - 3.5 * sa, b - 3.5 * sb),
    rawHi = Math.max(a + 3.5 * sa, b + 3.5 * sb),
    rawSpan = rawHi - rawLo;
  const padding =
    rawSpan > 0
      ? Math.max(
          rawSpan * 0.04,
          Number.EPSILON * Math.max(Math.abs(a), Math.abs(b)) * 8,
          Number.MIN_VALUE * 16,
        )
      : Math.max(Math.abs(a) * 0.03, Math.abs(b) * 0.03, 0.5);
  const lo = rawLo - padding,
    hi = rawHi + padding,
    span = hi - lo,
    width = Math.max(260, chartWidth),
    height = width < 420 ? 250 : 280,
    left = 48,
    right = width - 12,
    top = 30,
    bottom = height - 55,
    plotWidth = right - left;
  if (!Number.isFinite(span) || span <= 0)
    return (
      <div ref={chartRef} className="empty-small">
        This outcome exceeds the plot’s numerical range. Exact moments remain
        available below.
      </div>
    );
  const x = (v: number) => left + ((v - lo) / span) * plotWidth;
  const density = (value: number, mean: number, sd: number) =>
    Math.exp(-0.5 * ((value - mean) / sd) ** 2) / (sd * Math.sqrt(2 * Math.PI));
  const peaks = distributions
    .filter((d) => d.sd > 0)
    .map((d) => 1 / (d.sd * Math.sqrt(2 * Math.PI)));
  const peak = peaks.length ? Math.max(...peaks) * 1.08 : 1;
  const y = (v: number) => bottom - (v / peak) * (bottom - top);
  const tickCount = width < 420 ? 3 : 5,
    ticks = Array.from(
      { length: tickCount },
      (_, i) => lo + (i * span) / (tickCount - 1),
    );
  // Overlay the dashed conditioning curve last so identical answers still show both series.
  const plotSeries = [...distributions].reverse().map((d) => {
    if (d.sd === 0) return { ...d, curve: null };
    // Add samples around each mean so a narrow density is not lost on the shared scale.
    const locations = Array.from(
      { length: 161 },
      (_, i) => lo + (i * span) / 160,
    )
      .concat(
        Array.from({ length: 161 }, (_, i) => d.mean + d.sd * (i / 20 - 4)),
        d.mean,
      )
      .filter((value) => value >= lo && value <= hi)
      .sort((v, w) => v - w);
    const curve = locations
      .map(
        (value) =>
          `${x(value).toFixed(3)},${y(density(value, d.mean, d.sd)).toFixed(3)}`,
      )
      .join(" L");
    return { ...d, curve };
  });
  return (
    <div ref={chartRef} className="viz-distribution">
      <div className="viz-distribution-legend">
        {distributions.map((d) => (
          <span key={d.key} className={`viz-series-key viz-${d.key}`}>
            <i />
            {d.name}
            <strong>
              μ {fmt(d.mean)} ·{" "}
              {d.sd === 0 ? "fixed value" : `σ² ${fmt(d.sd * d.sd)}`}
            </strong>
          </span>
        ))}
      </div>
      <svg
        className="distribution-chart viz-density-chart"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`Conditional mean ${fmt(a)}, variance ${fmt(sa * sa)}; intervention mean ${fmt(b)}, variance ${fmt(sb * sb)}. Curves show Gaussian probability density; a dashed vertical line represents a point mass, not a finite density.`}
      >
        <text className="viz-axis-title" x={left} y="13">
          {peaks.length ? "PROBABILITY DENSITY" : "FIXED VALUES · POINT MASSES"}
        </text>
        {peaks.length > 0 &&
          [0, 0.5, 1].map((fraction) => (
            <g key={fraction}>
              <line
                className="viz-grid"
                x1={left}
                x2={right}
                y1={y(peak * fraction)}
                y2={y(peak * fraction)}
              />
              <text
                className="viz-tick"
                x={left - 9}
                y={y(peak * fraction) + 4}
                textAnchor="end"
              >
                {axisNumber(peak * fraction, peak / 2)}
              </text>
            </g>
          ))}
        {plotSeries
          .filter((d) => d.curve)
          .map((d) => (
            <path
              key={d.key}
              className={`viz-density-fill viz-${d.key}`}
              d={`M${left},${bottom} L${d.curve} L${right},${bottom} Z`}
            />
          ))}
        {plotSeries.map((d) =>
          d.curve ? (
            <g key={d.key} className={`viz-density-series viz-${d.key}`}>
              <path className="viz-density-line" d={`M${d.curve}`} />
              <title>
                {d.name}: Gaussian mean {fmt(d.mean)}, variance{" "}
                {fmt(d.sd * d.sd)}.
              </title>
            </g>
          ) : (
            <g key={d.key} className={`viz-density-series viz-${d.key}`}>
              <line
                className="viz-point-mass"
                x1={x(d.mean)}
                x2={x(d.mean)}
                y1={bottom}
                y2={top + 8}
              />
              <path
                className="viz-point-cap"
                d={`M${x(d.mean) - 5} ${top + 13} L${x(d.mean)} ${top + 8} L${x(d.mean) + 5} ${top + 13}`}
              />
              <title>
                {d.name}: all probability mass at {fmt(d.mean)}; variance zero.
              </title>
            </g>
          ),
        )}
        <line
          className="viz-axis"
          x1={left}
          x2={right}
          y1={bottom}
          y2={bottom}
        />
        {ticks.map((value, i) => (
          <g key={i}>
            <line
              className="viz-axis"
              x1={x(value)}
              x2={x(value)}
              y1={bottom}
              y2={bottom + 6}
            />
            <text
              className="viz-tick"
              x={x(value)}
              y={bottom + 24}
              textAnchor={
                i === 0 ? "start" : i === tickCount - 1 ? "end" : "middle"
              }
            >
              {axisNumber(value, span / (tickCount - 1))}
            </text>
          </g>
        ))}
        <text
          className="viz-axis-title"
          x={right}
          y={height - 10}
          textAnchor="end"
        >
          OUTCOME · ORIGINAL UNITS
        </text>
      </svg>
    </div>
  );
}

export function JsonDetails({
  title,
  value,
  open = false,
}: {
  title: string;
  value: unknown;
  open?: boolean;
}) {
  return (
    <details className="json-details" open={open}>
      <summary>
        {title}
        <Icon name="chevron" size={13} />
      </summary>
      <pre>{pretty(value)}</pre>
    </details>
  );
}
