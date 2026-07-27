"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  backfillHistory,
  fetchHistory,
  type HistoryDay,
  type SavedLocation,
} from "@/lib/weather/api";

/** Fixed 30-day window — longer ranges compress the daily swing into noise. */
const RANGE_DAYS = 30;
/** Backfill wider than the window so the chart is full immediately. */
const BACKFILL_DAYS = 90;

type Metric = "temp" | "precip" | "wind";

const METRICS: { id: Metric; label: string }[] = [
  { id: "temp", label: "Temp" },
  { id: "precip", label: "Rain" },
  { id: "wind", label: "Wind" },
];

/**
 * Plot geometry in SVG user units.
 *
 * Note this SVG keeps its aspect ratio (no preserveAspectRatio="none"):
 * stretching the viewBox to fill the width would non-uniformly scale the
 * point markers and axis text into ovals and squashed glyphs.
 */
const W = 760;
const H = 230;
const PAD_L = 40;
const PAD_R = 12;
const PAD_T = 12;
const PAD_B = 30;

interface Props {
  locations: SavedLocation[];
}

export default function WeatherTimeline({ locations }: Props) {
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [metric, setMetric] = useState<Metric>("temp");
  const [history, setHistory] = useState<HistoryDay[]>([]);
  const [loading, setLoading] = useState(false);
  const [backfilling, setBackfilling] = useState(false);
  /** Index of the day under the cursor, for the readout. */
  const [hover, setHover] = useState<number | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (locations.length === 0) { setSelectedId(null); return; }
    if (!locations.some((l) => l.id === selectedId)) setSelectedId(locations[0].id);
  }, [locations, selectedId]);

  const load = useCallback(async (id: number) => {
    setLoading(true);
    try {
      setHistory(await fetchHistory(id, RANGE_DAYS));
    } catch {
      setHistory([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (selectedId != null) load(selectedId);
  }, [selectedId, load]);

  async function runBackfill() {
    if (selectedId == null) return;
    setBackfilling(true);
    try {
      await backfillHistory(selectedId, BACKFILL_DAYS);
      await load(selectedId);
    } catch {
      /* Leave the empty state up; switching city still works. */
    } finally {
      setBackfilling(false);
    }
  }

  if (locations.length === 0) return null;

  const selected = locations.find((l) => l.id === selectedId);

  // Filter per metric, so a gap in an unrelated column doesn't drop the day.
  const usable = history.filter((d) =>
    metric === "temp" ? d.tempMax != null && d.tempMin != null
      : metric === "precip" ? d.precipitation != null
      : d.windSpeedMax != null
  );

  const values =
    metric === "temp"
      ? usable.flatMap((d) => [d.tempMax as number, d.tempMin as number])
      : usable.map((d) =>
          (metric === "precip" ? d.precipitation : d.windSpeedMax) as number
        );

  // Rain and wind read wrong on a floating baseline — anchor them at zero.
  const rawMin = values.length ? Math.min(...values) : 0;
  const rawMax = values.length ? Math.max(...values) : 1;
  // Pad the temperature range so the extremes aren't glued to the frame.
  const min = metric === "temp" ? Math.floor(rawMin - 1) : 0;
  const max = metric === "temp" ? Math.ceil(rawMax + 1) : rawMax || 1;
  const span = max - min || 1;

  const x = (i: number) =>
    PAD_L + (i / Math.max(usable.length - 1, 1)) * (W - PAD_L - PAD_R);
  const y = (v: number) => PAD_T + (1 - (v - min) / span) * (H - PAD_T - PAD_B);

  const unit = metric === "temp" ? "°C" : metric === "precip" ? "mm" : "km/h";

  /** Four evenly-spaced gridlines, so values can be read off the chart. */
  const ticks = [0, 1, 2, 3].map((i) => min + (span * i) / 3);

  /** Map a pointer position to the nearest day index. */
  function onMove(e: React.PointerEvent<SVGSVGElement>) {
    const svg = svgRef.current;
    if (!svg || usable.length === 0) return;
    const rect = svg.getBoundingClientRect();
    // Convert client px to viewBox units — the SVG scales, so this cannot
    // assume 1:1.
    const vx = ((e.clientX - rect.left) / rect.width) * W;
    const ratio = (vx - PAD_L) / (W - PAD_L - PAD_R);
    const idx = Math.round(ratio * (usable.length - 1));
    setHover(idx >= 0 && idx < usable.length ? idx : null);
  }

  const active = hover != null ? usable[hover] : null;

  function pointValue(d: HistoryDay): number {
    return (metric === "precip" ? d.precipitation : d.windSpeedMax) as number;
  }

  function renderPlot() {
    if (metric === "precip") {
      const slot = (W - PAD_L - PAD_R) / Math.max(usable.length, 1);
      const barW = Math.max(slot * 0.62, 1);
      return usable.map((d, i) => {
        const top = y(d.precipitation as number);
        return (
          <rect
            key={d.date}
            x={x(i) - barW / 2}
            y={top}
            width={barW}
            height={Math.max(H - PAD_B - top, 0)}
            className={`wx-timeline-bar${hover === i ? " is-hover" : ""}`}
          />
        );
      });
    }

    if (metric === "wind") {
      const path = usable
        .map((d, i) => `${i === 0 ? "M" : "L"}${x(i)},${y(pointValue(d))}`)
        .join(" ");
      return (
        <>
          <path d={path} className="wx-timeline-line wx-timeline-wind" />
          {usable.map((d, i) => (
            <circle key={d.date} cx={x(i)} cy={y(pointValue(d))}
              r={hover === i ? 3.5 : 2} className="wx-timeline-dot wx-timeline-dot-wind" />
          ))}
        </>
      );
    }

    const band =
      usable.map((d, i) => `${i === 0 ? "M" : "L"}${x(i)},${y(d.tempMax as number)}`).join(" ") +
      " " +
      usable
        .slice()
        .reverse()
        .map((d, i) => `L${x(usable.length - 1 - i)},${y(d.tempMin as number)}`)
        .join(" ") +
      " Z";
    const line = (key: "tempMax" | "tempMin") =>
      usable.map((d, i) => `${i === 0 ? "M" : "L"}${x(i)},${y(d[key] as number)}`).join(" ");

    return (
      <>
        <path d={band} className="wx-timeline-band" />
        <path d={line("tempMax")} className="wx-timeline-line wx-timeline-max" />
        <path d={line("tempMin")} className="wx-timeline-line wx-timeline-min" />
        {usable.map((d, i) => (
          <g key={d.date}>
            <circle cx={x(i)} cy={y(d.tempMax as number)} r={hover === i ? 3.5 : 2}
              className="wx-timeline-dot wx-timeline-dot-max" />
            <circle cx={x(i)} cy={y(d.tempMin as number)} r={hover === i ? 3.5 : 2}
              className="wx-timeline-dot wx-timeline-dot-min" />
          </g>
        ))}
      </>
    );
  }

  /** Readout for the hovered day, falling back to a period summary. */
  function readout() {
    if (active) {
      const when = new Date(active.date + "T00:00:00").toLocaleDateString(undefined, {
        month: "short", day: "numeric",
      });
      if (metric === "temp")
        return `${when} — high ${active.tempMax}°C, low ${active.tempMin}°C`;
      if (metric === "precip")
        return `${when} — ${(active.precipitation ?? 0).toFixed(1)} mm`;
      return `${when} — ${Math.round(active.windSpeedMax ?? 0)} km/h`;
    }
    if (!usable.length) return "";
    if (metric === "temp")
      return `high ${Math.round(rawMax)}°C · low ${Math.round(rawMin)}°C · hover for a day`;
    if (metric === "precip") {
      const total = usable.reduce((s, d) => s + (d.precipitation ?? 0), 0);
      const wet = usable.filter((d) => (d.precipitation ?? 0) > 0.1).length;
      return `${total.toFixed(0)} mm total · ${wet} wet days · hover for a day`;
    }
    const avg = values.reduce((s, v) => s + v, 0) / values.length;
    return `peak ${Math.round(rawMax)} · avg ${Math.round(avg)} km/h · hover for a day`;
  }

  /** A handful of date labels — one per ~week, plus the last day. */
  const xLabels = usable
    .map((d, i) => ({ d, i }))
    .filter(({ i }) => i % 7 === 0 || i === usable.length - 1);

  return (
    <div className="wx-timeline">
      <div className="wx-timeline-head">
        <span className="wx-timeline-title">Last {RANGE_DAYS} days</span>
        <div className="wx-timeline-controls">
          <select
            className="wx-timeline-select"
            value={selectedId ?? ""}
            onChange={(e) => setSelectedId(Number(e.target.value))}
          >
            {locations.map((l) => (
              <option key={l.id} value={l.id}>
                {l.name}{l.country ? `, ${l.country}` : ""}
              </option>
            ))}
          </select>
          {METRICS.map((m) => (
            <button
              key={m.id}
              className={`wx-timeline-btn${metric === m.id ? " active" : ""}`}
              onClick={() => { setMetric(m.id); setHover(null); }}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="wx-timeline-empty">Loading…</div>
      ) : usable.length < 2 ? (
        <div className="wx-timeline-empty">
          No history stored for {selected?.name ?? "this city"} yet.
          <button className="wx-timeline-btn" onClick={runBackfill} disabled={backfilling}
            style={{ marginLeft: 8 }}>
            {backfilling ? "Fetching…" : "Load history"}
          </button>
        </div>
      ) : (
        <>
          <svg
            ref={svgRef}
            className="wx-timeline-svg"
            viewBox={`0 0 ${W} ${H}`}
            role="img"
            aria-label={`${metric} history for ${selected?.name}`}
            onPointerMove={onMove}
            onPointerLeave={() => setHover(null)}
          >
            {/* Gridlines first, so data draws over them. */}
            {ticks.map((t, i) => (
              <g key={i}>
                <line x1={PAD_L} x2={W - PAD_R} y1={y(t)} y2={y(t)}
                  className="wx-timeline-grid" />
                <text x={PAD_L - 6} y={y(t) + 3} className="wx-timeline-axis"
                  textAnchor="end">
                  {metric === "precip" ? t.toFixed(1) : Math.round(t)}
                </text>
              </g>
            ))}

            {renderPlot()}

            {/* Crosshair on the hovered day. */}
            {hover != null && (
              <line x1={x(hover)} x2={x(hover)} y1={PAD_T} y2={H - PAD_B}
                className="wx-timeline-crosshair" />
            )}

            {xLabels.map(({ d, i }) => (
              <text key={d.date} x={x(i)} y={H - PAD_B + 14}
                className="wx-timeline-axis" textAnchor="middle">
                {d.date.slice(5)}
              </text>
            ))}
          </svg>
          <div className="wx-timeline-foot">
            <span className="wx-timeline-readout">{readout()}</span>
            <span className="wx-timeline-unit">{unit}</span>
          </div>
        </>
      )}
    </div>
  );
}
