import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  ColorType,
  LineStyle,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type MouseEventParams,
  type Time,
  type UTCTimestamp,
} from "lightweight-charts";
import {
  getBars,
  getInstruments,
  type BarData,
  type Instrument,
} from "../api/market-data";

const TIMEFRAMES = [
  { label: "1m", value: "1m" },
  { label: "3m", value: "3m" },
  { label: "5m", value: "5m" },
  { label: "15m", value: "15m" },
  { label: "30m", value: "30m" },
  { label: "1H", value: "1h" },
  { label: "4H", value: "4h" },
  { label: "Daily", value: "1d" },
] as const;
const SESSIONS = [
  { value: "all", label: "All" },
  { value: "RTH", label: "RTH" },
  { value: "ETH", label: "ETH" },
];
type Tool = "cursor" | "trend" | "horizontal" | "rectangle";
type Point = { time: UTCTimestamp; price: number };
type Drawing = { id: string; type: Exclude<Tool, "cursor">; start: Point; end: Point };
type Zone = { id: string; start: UTCTimestamp; end: UTCTimestamp; top: number; bottom: number; color: string; label: string };
type StructureEvent = { time: UTCTimestamp; position: "aboveBar" | "belowBar"; color: string; shape: "arrowUp" | "arrowDown" | "circle"; text: string };
type Hover = { bar: BarData; ema9?: number; ema21?: number; ema50?: number; ema200?: number };

function toTime(timestamp: string): UTCTimestamp {
  return Math.floor(new Date(timestamp).getTime() / 1000) as UTCTimestamp;
}
function isoDate(d: Date): string { return d.toISOString().slice(0, 10); }
function number(value: number | undefined, decimals = 2) { return value == null || !Number.isFinite(value) ? "—" : value.toFixed(decimals); }
function formatBarCount(n: number): string { return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n); }
function formatEt(timestamp: string) {
  return new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false }).format(new Date(timestamp));
}
function etParts(timestamp: string) {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: "America/New_York", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).formatToParts(new Date(timestamp));
  const get = (name: string) => parts.find((item) => item.type === name)?.value ?? "00";
  return { day: `${get("year")}-${get("month")}-${get("day")}`, hour: Number(get("hour")), minute: Number(get("minute")) };
}
function isRth(bar: BarData) {
  if (bar.session?.toUpperCase() === "RTH") return true;
  const { hour, minute } = etParts(bar.timestamp);
  return (hour > 9 || (hour === 9 && minute >= 30)) && hour < 16;
}
function ema(bars: BarData[], period: number) {
  const multiplier = 2 / (period + 1);
  let current = bars[0]?.close ?? 0;
  return bars.map((bar, index) => {
    current = index === 0 ? bar.close : (bar.close - current) * multiplier + current;
    return current;
  });
}
function averageRange(bars: BarData[], from: number, lookback = 12) {
  const start = Math.max(0, from - lookback);
  const count = Math.max(1, from - start);
  return bars.slice(start, from).reduce((sum, bar) => sum + bar.high - bar.low, 0) / count;
}
function swingPoints(bars: BarData[], span = 3) {
  const highs: number[] = []; const lows: number[] = [];
  for (let i = span; i < bars.length - span; i += 1) {
    const before = bars.slice(i - span, i); const after = bars.slice(i + 1, i + span + 1);
    if (before.every((bar) => bar.high < bars[i].high) && after.every((bar) => bar.high <= bars[i].high)) highs.push(i);
    if (before.every((bar) => bar.low > bars[i].low) && after.every((bar) => bar.low >= bars[i].low)) lows.push(i);
  }
  return { highs, lows };
}
function periodKey(timestamp: string, period: "day" | "week" | "month") {
  const date = new Date(timestamp);
  if (period === "month") return `${date.getUTCFullYear()}-${date.getUTCMonth()}`;
  if (period === "week") {
    const copy = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()));
    copy.setUTCDate(copy.getUTCDate() - ((copy.getUTCDay() + 6) % 7));
    return copy.toISOString().slice(0, 10);
  }
  return etParts(timestamp).day;
}
function previousPeriodLevels(bars: BarData[], period: "day" | "week" | "month") {
  const grouped = new Map<string, BarData[]>();
  bars.forEach((bar) => {
    const key = periodKey(bar.timestamp, period);
    grouped.set(key, [...(grouped.get(key) ?? []), bar]);
  });
  const groups = [...grouped.values()];
  if (groups.length < 2) return undefined;
  const prior = groups[groups.length - 2];
  return { high: Math.max(...prior.map((bar) => bar.high)), low: Math.min(...prior.map((bar) => bar.low)) };
}
function sessionLevels(bars: BarData[]) {
  const rth = bars.filter(isRth); const last = rth[rth.length - 1];
  if (!last) return undefined;
  const day = etParts(last.timestamp).day;
  const session = rth.filter((bar) => etParts(bar.timestamp).day === day);
  return { high: Math.max(...session.map((bar) => bar.high)), low: Math.min(...session.map((bar) => bar.low)) };
}
function findFvgs(bars: BarData[]): Zone[] {
  const zones: Zone[] = [];
  for (let i = 2; i < bars.length; i += 1) {
    const left = bars[i - 2]; const current = bars[i];
    if (current.low > left.high) zones.push({ id: `fvg-b-${i}`, start: toTime(left.timestamp), end: toTime(current.timestamp), top: current.low, bottom: left.high, color: "rgba(34,197,94,.14)", label: "FVG" });
    if (current.high < left.low) zones.push({ id: `fvg-s-${i}`, start: toTime(left.timestamp), end: toTime(current.timestamp), top: left.low, bottom: current.high, color: "rgba(239,68,68,.14)", label: "FVG" });
  }
  return zones.slice(-18);
}
function findOrderBlocks(bars: BarData[]): Zone[] {
  const zones: Zone[] = [];
  for (let i = 4; i < bars.length; i += 1) {
    const bar = bars[i]; const impulse = Math.abs(bar.close - bar.open) > averageRange(bars, i) * 1.35;
    if (!impulse) continue;
    const bullish = bar.close > bar.open;
    for (let j = i - 1; j >= Math.max(0, i - 6); j -= 1) {
      const candidate = bars[j];
      if ((bullish && candidate.close < candidate.open) || (!bullish && candidate.close > candidate.open)) {
        zones.push({ id: `ob-${i}-${j}`, start: toTime(candidate.timestamp), end: toTime(bar.timestamp), top: candidate.high, bottom: candidate.low, color: bullish ? "rgba(59,130,246,.13)" : "rgba(168,85,247,.13)", label: bullish ? "Bull OB" : "Bear OB" });
        break;
      }
    }
  }
  return zones.slice(-12);
}
function liquidityLevels(bars: BarData[]) {
  const { highs, lows } = swingPoints(bars); const values = [...highs.map((index) => bars[index].high), ...lows.map((index) => bars[index].low)];
  const tolerance = Math.max(0.01, (Math.max(...bars.map((bar) => bar.high)) - Math.min(...bars.map((bar) => bar.low))) * 0.0025);
  const clusters: { price: number; touches: number }[] = [];
  values.forEach((value) => {
    const found = clusters.find((cluster) => Math.abs(cluster.price - value) <= tolerance);
    if (found) { found.price = (found.price * found.touches + value) / (found.touches + 1); found.touches += 1; }
    else clusters.push({ price: value, touches: 1 });
  });
  return clusters.filter((cluster) => cluster.touches >= 2).sort((a, b) => b.touches - a.touches).slice(0, 6);
}
function structureEvents(bars: BarData[]): StructureEvent[] {
  const { highs, lows } = swingPoints(bars); const events: StructureEvent[] = []; let trend: "bull" | "bear" | undefined;
  let lastHigh: number | undefined; let lastLow: number | undefined;
  const highSet = new Set(highs); const lowSet = new Set(lows);
  for (let i = 0; i < bars.length; i += 1) {
    if (highSet.has(i)) lastHigh = bars[i].high;
    if (lowSet.has(i)) lastLow = bars[i].low;
    if (lastHigh != null && bars[i].close > lastHigh && (i === 0 || bars[i - 1].close <= lastHigh)) {
      const shift = trend === "bear";
      events.push({ time: toTime(bars[i].timestamp), position: "belowBar", color: shift ? "#f59e0b" : "#22c55e", shape: "arrowUp", text: shift ? "CHoCH / MSS" : "BOS" }); trend = "bull";
    }
    if (lastLow != null && bars[i].close < lastLow && (i === 0 || bars[i - 1].close >= lastLow)) {
      const shift = trend === "bull";
      events.push({ time: toTime(bars[i].timestamp), position: "aboveBar", color: shift ? "#f59e0b" : "#ef4444", shape: "arrowDown", text: shift ? "CHoCH / MSS" : "BOS" }); trend = "bear";
    }
  }
  return events.slice(-30);
}
function smtEvents(bars: BarData[], correlated: BarData[]): StructureEvent[] {
  if (!correlated.length) return [];
  const length = Math.min(bars.length, correlated.length); const events: StructureEvent[] = [];
  for (let i = 8; i < length; i += 1) {
    const prior = bars.slice(i - 8, i); const otherPrior = correlated.slice(i - 8, i);
    const higherHigh = bars[i].high > Math.max(...prior.map((bar) => bar.high));
    const lowerLow = bars[i].low < Math.min(...prior.map((bar) => bar.low));
    const confirmsHigh = correlated[i].high > Math.max(...otherPrior.map((bar) => bar.high));
    const confirmsLow = correlated[i].low < Math.min(...otherPrior.map((bar) => bar.low));
    if (higherHigh && !confirmsHigh) events.push({ time: toTime(bars[i].timestamp), position: "aboveBar", color: "#06b6d4", shape: "circle", text: "SMT" });
    if (lowerLow && !confirmsLow) events.push({ time: toTime(bars[i].timestamp), position: "belowBar", color: "#06b6d4", shape: "circle", text: "SMT" });
  }
  return events.slice(-12);
}

function ChartToolbar({ tool, setTool, onReset }: { tool: Tool; setTool: (tool: Tool) => void; onReset: () => void }) {
  const tools: { id: Tool; label: string; icon: string }[] = [
    { id: "cursor", label: "Cursor", icon: "⌁" }, { id: "trend", label: "Trendline", icon: "╱" }, { id: "horizontal", label: "Horizontal line", icon: "—" }, { id: "rectangle", label: "Rectangle", icon: "▭" },
  ];
  return <div className="flex items-center gap-1 rounded border border-slate-700 bg-slate-900/95 p-1 shadow-lg">
    {tools.map((item) => <button key={item.id} title={item.label} onClick={() => setTool(item.id)} className={`rounded px-2 py-1 text-sm ${tool === item.id ? "bg-cyan-500/20 text-cyan-300" : "text-slate-400 hover:bg-slate-800 hover:text-slate-100"}`}>{item.icon}</button>)}
    <span className="mx-1 h-4 w-px bg-slate-700" />
    <button title="Reset chart view" onClick={onReset} className="rounded px-2 py-1 text-xs text-slate-300 hover:bg-slate-800">Reset</button>
  </div>;
}

export default function Charts() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [instruments, setInstruments] = useState<Instrument[]>([]);
  const [symbol, setSymbol] = useState(searchParams.get("symbol") || "ES");
  const [timeframe, setTimeframe] = useState("5m");
  const [session, setSession] = useState("all");
  const [startDate, setStartDate] = useState(() => { const date = new Date(); date.setDate(date.getDate() - 7); return isoDate(date); });
  const [endDate, setEndDate] = useState(() => isoDate(new Date()));
  const [bars, setBars] = useState<BarData[]>([]);
  const [correlatedBars, setCorrelatedBars] = useState<BarData[]>([]);
  const [loading, setLoading] = useState(true); const [error, setError] = useState("");
  const [hover, setHover] = useState<Hover>(); const [tool, setTool] = useState<Tool>("cursor");
  const [drawings, setDrawings] = useState<Drawing[]>([]); const [draft, setDraft] = useState<Drawing>();
  const [overlayVersion, setOverlayVersion] = useState(0);
  const chartRef = useRef<HTMLDivElement>(null); const chartApiRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null); const drawingSeriesRef = useRef<ISeriesApi<"Line">[]>([]);
  const pointerStart = useRef<Point | null>(null);

  useEffect(() => { getInstruments().then((result) => setInstruments(result.instruments)).catch(() => undefined); }, []);
  useEffect(() => { setSearchParams({ symbol }, { replace: true }); }, [symbol, setSearchParams]);

  const fetchBars = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true); setError("");
    const start = startDate ? `${startDate}T00:00:00` : undefined; const end = endDate ? `${endDate}T23:59:59` : undefined;
    const related = symbol === "NQ" ? "ES" : "NQ";
    try {
      const [response, correlation] = await Promise.all([getBars(symbol, timeframe, start, end, session), getBars(related, timeframe, start, end, session).catch(() => null)]);
      setBars(response.bars); setCorrelatedBars(correlation?.bars ?? []);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Unable to load market data"); }
    finally { if (!quiet) setLoading(false); }
  }, [symbol, timeframe, session, startDate, endDate]);
  useEffect(() => { void fetchBars(); }, [fetchBars]);
  useEffect(() => { const timer = window.setInterval(() => { void fetchBars(true); }, 5000); return () => window.clearInterval(timer); }, [fetchBars]);

  const indicators = useMemo(() => ({ ema9: ema(bars, 9), ema21: ema(bars, 21), ema50: ema(bars, 50), ema200: ema(bars, 200) }), [bars]);
  const fvgZones = useMemo(() => findFvgs(bars), [bars]); const orderBlocks = useMemo(() => findOrderBlocks(bars), [bars]);
  const events = useMemo(() => [...structureEvents(bars), ...smtEvents(bars, correlatedBars)].sort((a, b) => a.time - b.time), [bars, correlatedBars]);
  const levels = useMemo(() => ({ session: sessionLevels(bars), day: previousPeriodLevels(bars, "day"), week: previousPeriodLevels(bars, "week"), month: previousPeriodLevels(bars, "month"), liquidity: bars.length ? liquidityLevels(bars) : [] }), [bars]);

  useEffect(() => {
    if (!chartRef.current || !bars.length) return;
    chartApiRef.current?.remove(); drawingSeriesRef.current = [];
    const chart = createChart(chartRef.current, {
      width: chartRef.current.clientWidth, height: chartRef.current.clientHeight || 600,
      layout: { background: { type: ColorType.Solid, color: "#090f1d" }, textColor: "#94a3b8", fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace" },
      grid: { vertLines: { color: "#172033" }, horzLines: { color: "#172033" } },
      crosshair: { mode: 0, vertLine: { color: "#64748b", labelBackgroundColor: "#1e293b" }, horzLine: { color: "#64748b", labelBackgroundColor: "#1e293b" } },
      rightPriceScale: { borderColor: "#263247", scaleMargins: { top: 0.08, bottom: 0.22 } },
      timeScale: { borderColor: "#263247", timeVisible: true, secondsVisible: false, rightOffset: 4 },
      handleScroll: { mouseWheel: true, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: true }, handleScale: { mouseWheel: true, pinch: true, axisPressedMouseMove: true },
    });
    chartApiRef.current = chart;
    const candle = chart.addCandlestickSeries({ upColor: "#22c55e", downColor: "#ef4444", borderUpColor: "#22c55e", borderDownColor: "#ef4444", wickUpColor: "#22c55e", wickDownColor: "#ef4444", priceLineVisible: true });
    candleRef.current = candle;
    candle.setData(bars.map((bar) => ({ time: toTime(bar.timestamp), open: bar.open, high: bar.high, low: bar.low, close: bar.close })));
    const volume = chart.addHistogramSeries({ priceFormat: { type: "volume" }, priceScaleId: "volume", lastValueVisible: false, priceLineVisible: false });
    chart.priceScale("volume").applyOptions({ scaleMargins: { top: 0.83, bottom: 0 } });
    volume.setData(bars.map((bar) => ({ time: toTime(bar.timestamp), value: bar.volume, color: bar.close >= bar.open ? "rgba(34,197,94,.42)" : "rgba(239,68,68,.42)" })));
    const addLine = (values: number[], color: string, width: 1 | 2 | 3 | 4 = 1) => { const series = chart.addLineSeries({ color, lineWidth: width, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false }); series.setData(bars.map((bar, index) => ({ time: toTime(bar.timestamp), value: values[index] }))); return series; };
    addLine(indicators.ema9, "#38bdf8"); addLine(indicators.ema21, "#fb923c"); addLine(indicators.ema50, "#a855f7"); addLine(indicators.ema200, "#ef4444", 2);
    const vwap = chart.addLineSeries({ color: "#fbbf24", lineWidth: 1, lineStyle: LineStyle.Dashed, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
    vwap.setData(bars.filter((bar) => bar.vwap > 0).map((bar) => ({ time: toTime(bar.timestamp), value: bar.vwap })));
    const priceLine = (price: number | undefined, title: string, color: string, style: LineStyle) => { if (price != null) candle.createPriceLine({ price, color, lineWidth: 1, lineStyle: style, axisLabelVisible: true, title }); };
    priceLine(levels.session?.high, "RTH H", "#60a5fa", LineStyle.Dashed); priceLine(levels.session?.low, "RTH L", "#60a5fa", LineStyle.Dashed);
    priceLine(levels.day?.high, "PDH", "#f8fafc", LineStyle.Dotted); priceLine(levels.day?.low, "PDL", "#f8fafc", LineStyle.Dotted);
    priceLine(levels.week?.high, "PWH", "#818cf8", LineStyle.Dashed); priceLine(levels.week?.low, "PWL", "#818cf8", LineStyle.Dashed);
    priceLine(levels.month?.high, "PMH", "#e879f9", LineStyle.Dashed); priceLine(levels.month?.low, "PML", "#e879f9", LineStyle.Dashed);
    levels.liquidity.forEach((level) => priceLine(level.price, `LQ ×${level.touches}`, "#14b8a6", LineStyle.Dotted));
    if (bars.length) { const high = Math.max(...bars.map((bar) => bar.high)); const low = Math.min(...bars.map((bar) => bar.low)); priceLine((high + low) / 2, "EQ", "#64748b", LineStyle.Dotted); }
    candle.setMarkers(events);
    const onCrosshair = (param: MouseEventParams<Time>) => {
      if (!param.time) { setHover(undefined); return; }
      const index = bars.findIndex((bar) => toTime(bar.timestamp) === param.time);
      if (index >= 0) setHover({ bar: bars[index], ema9: indicators.ema9[index], ema21: indicators.ema21[index], ema50: indicators.ema50[index], ema200: indicators.ema200[index] });
    };
    chart.subscribeCrosshairMove(onCrosshair);
    const redraw = () => setOverlayVersion((version) => version + 1);
    chart.timeScale().subscribeVisibleTimeRangeChange(redraw);
    const resize = new ResizeObserver(([entry]) => { chart.applyOptions({ width: entry.contentRect.width, height: entry.contentRect.height }); redraw(); }); resize.observe(chartRef.current);
    chart.timeScale().fitContent();
    return () => { resize.disconnect(); chart.unsubscribeCrosshairMove(onCrosshair); chart.timeScale().unsubscribeVisibleTimeRangeChange(redraw); chart.remove(); chartApiRef.current = null; candleRef.current = null; };
  }, [bars, indicators, levels, events]);

  useEffect(() => {
    const chart = chartApiRef.current; if (!chart) return;
    drawingSeriesRef.current.forEach((series) => chart.removeSeries(series)); drawingSeriesRef.current = [];
    drawings.filter((drawing) => drawing.type !== "rectangle").forEach((drawing) => {
      if (drawing.type === "horizontal") { candleRef.current?.createPriceLine({ price: drawing.start.price, color: "#f8fafc", lineWidth: 1, lineStyle: LineStyle.Solid, title: "Manual" }); return; }
      const series = chart.addLineSeries({ color: "#e2e8f0", lineWidth: 2, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
      series.setData([{ time: drawing.start.time, value: drawing.start.price }, { time: drawing.end.time, value: drawing.end.price }]); drawingSeriesRef.current.push(series);
    });
    setOverlayVersion((version) => version + 1);
  }, [drawings]);

  const screenZone = useCallback((zone: Zone) => {
    const chart = chartApiRef.current; const candle = candleRef.current; if (!chart || !candle) return null;
    const left = chart.timeScale().timeToCoordinate(zone.start); const right = chart.timeScale().timeToCoordinate(zone.end);
    const top = candle.priceToCoordinate(zone.top); const bottom = candle.priceToCoordinate(zone.bottom);
    if (left == null || right == null || top == null || bottom == null) return null;
    return { left: Math.min(left, right), top: Math.min(top, bottom), width: Math.max(2, Math.abs(right - left)), height: Math.max(2, Math.abs(bottom - top)) };
  }, []);
  const pointerPoint = useCallback((event: React.PointerEvent<HTMLDivElement>): Point | null => {
    const container = chartRef.current; const chart = chartApiRef.current; const candle = candleRef.current; if (!container || !chart || !candle) return null;
    const rect = container.getBoundingClientRect(); const x = event.clientX - rect.left; const y = event.clientY - rect.top;
    const time = chart.timeScale().coordinateToTime(x); const price = candle.coordinateToPrice(y);
    return typeof time === "number" && price != null ? { time: time as UTCTimestamp, price } : null;
  }, []);
  const onPointerDown = (event: React.PointerEvent<HTMLDivElement>) => { if (tool === "cursor") return; const point = pointerPoint(event); if (!point) return; pointerStart.current = point; setDraft({ id: "draft", type: tool, start: point, end: point }); event.currentTarget.setPointerCapture(event.pointerId); };
  const onPointerMove = (event: React.PointerEvent<HTMLDivElement>) => { if (!pointerStart.current) return; const point = pointerPoint(event); if (point && tool !== "cursor") setDraft({ id: "draft", type: tool, start: pointerStart.current, end: point }); };
  const onPointerUp = (event: React.PointerEvent<HTMLDivElement>) => { if (!pointerStart.current || tool === "cursor") return; const end = pointerPoint(event) ?? pointerStart.current; const type = tool as Exclude<Tool, "cursor">; setDrawings((current) => [...current, { id: `${Date.now()}-${current.length}`, type, start: pointerStart.current!, end: type === "horizontal" ? { ...end, price: pointerStart.current!.price } : end }]); pointerStart.current = null; setDraft(undefined); setTool("cursor"); };
  const resetChart = () => { chartApiRef.current?.timeScale().fitContent(); setDrawings([]); setOverlayVersion((version) => version + 1); };

  const allZones = [...fvgZones, ...orderBlocks]; const range = bars.length ? { high: Math.max(...bars.map((bar) => bar.high)), low: Math.min(...bars.map((bar) => bar.low)) } : undefined;
  const first = bars[0]; const last = bars[bars.length - 1];
  return <div className="flex min-h-[calc(100vh-5rem)] flex-col bg-slate-950">
    <div className="flex flex-wrap items-end gap-4 border-b border-slate-800 bg-slate-900/60 px-4 py-3">
      <div><label className="mb-1 block text-[10px] font-bold uppercase tracking-wider text-slate-500">Instrument</label><select value={symbol} onChange={(event) => setSymbol(event.target.value)} className="rounded border border-slate-700 bg-slate-900 px-3 py-1.5 text-sm font-semibold text-slate-100 focus:border-cyan-500 focus:outline-none">{instruments.length ? instruments.map((instrument) => <option key={instrument.symbol} value={instrument.symbol}>{instrument.symbol} — {instrument.name}</option>) : <option value={symbol}>{symbol}</option>}</select></div>
      <div><label className="mb-1 block text-[10px] font-bold uppercase tracking-wider text-slate-500">Timeframe</label><div className="flex flex-wrap gap-1">{TIMEFRAMES.map((item) => <button key={item.value} onClick={() => setTimeframe(item.value)} className={`rounded px-2 py-1.5 text-xs font-semibold ${timeframe === item.value ? "bg-cyan-500 text-slate-950" : "bg-slate-800 text-slate-400 hover:bg-slate-700 hover:text-slate-100"}`}>{item.label}</button>)}</div></div>
      <div><label className="mb-1 block text-[10px] font-bold uppercase tracking-wider text-slate-500">Session</label><div className="flex gap-1">{SESSIONS.map((item) => <button key={item.value} onClick={() => setSession(item.value)} className={`rounded px-2 py-1.5 text-xs ${session === item.value ? "bg-slate-200 text-slate-950" : "bg-slate-800 text-slate-400 hover:text-slate-100"}`}>{item.label}</button>)}</div></div>
      <div className="flex gap-2"><label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">From<input type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} className="mt-1 block rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-200" /></label><label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">To<input type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} className="mt-1 block rounded border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-200" /></label></div>
      <div className="ml-auto flex items-center gap-2 text-xs text-slate-500"><span className="h-2 w-2 animate-pulse rounded-full bg-emerald-400" />Auto-refresh 5s<button onClick={() => void fetchBars()} className="rounded border border-slate-700 px-2 py-1 text-slate-300 hover:bg-slate-800">Refresh</button></div>
    </div>
    <div className="relative min-h-[560px] flex-1">
      <div ref={chartRef} className="absolute inset-0" />
      {range && <div className="pointer-events-none absolute inset-x-0 top-0 bottom-[17%] overflow-hidden" key={overlayVersion}>
        {(() => { const mid = (range.high + range.low) / 2; const top = screenZone({ id: "premium", start: toTime(first.timestamp), end: toTime(last.timestamp), top: range.high, bottom: mid, color: "", label: "" }); const bottom = screenZone({ id: "discount", start: toTime(first.timestamp), end: toTime(last.timestamp), top: mid, bottom: range.low, color: "", label: "" }); return <>{top && <div className="absolute border border-rose-400/10 bg-rose-500/[.035]" style={top}><span className="absolute right-1 top-1 text-[9px] font-bold tracking-widest text-rose-300/50">PREMIUM</span></div>}{bottom && <div className="absolute border border-emerald-400/10 bg-emerald-500/[.035]" style={bottom}><span className="absolute right-1 bottom-1 text-[9px] font-bold tracking-widest text-emerald-300/50">DISCOUNT</span></div>}</>; })()}
        {allZones.map((zone) => { const box = screenZone(zone); return box ? <div key={zone.id} className="absolute border border-white/10" style={{ ...box, backgroundColor: zone.color }}><span className="absolute left-1 top-0 text-[9px] text-slate-300/80">{zone.label}</span></div> : null; })}
        {[...drawings.filter((drawing) => drawing.type === "rectangle"), ...(draft?.type === "rectangle" ? [draft] : [])].map((drawing) => { const box = screenZone({ id: drawing.id, start: drawing.start.time, end: drawing.end.time, top: drawing.start.price, bottom: drawing.end.price, color: "", label: "" }); return box ? <div key={drawing.id} className="absolute border border-slate-100 bg-slate-300/10" style={box} /> : null; })}
      </div>}
      <div className="absolute left-3 top-3 z-20"><ChartToolbar tool={tool} setTool={setTool} onReset={resetChart} /></div>
      {hover && <div className="pointer-events-none absolute right-4 top-3 z-20 grid grid-cols-3 gap-x-4 gap-y-1 rounded border border-slate-700 bg-slate-950/95 px-3 py-2 font-mono text-[11px] shadow-xl"><span className="col-span-3 text-cyan-300">{formatEt(hover.bar.timestamp)} ET</span><span>O <b className="text-slate-100">{number(hover.bar.open)}</b></span><span>H <b className="text-emerald-300">{number(hover.bar.high)}</b></span><span>L <b className="text-rose-300">{number(hover.bar.low)}</b></span><span>C <b className="text-slate-100">{number(hover.bar.close)}</b></span><span>V <b className="text-slate-100">{formatBarCount(hover.bar.volume)}</b></span><span>VWAP <b className="text-amber-300">{number(hover.bar.vwap)}</b></span><span className="text-sky-300">E9 {number(hover.ema9)}</span><span className="text-orange-300">E21 {number(hover.ema21)}</span><span className="text-purple-300">E50 {number(hover.ema50)}</span><span className="text-red-300">E200 {number(hover.ema200)}</span></div>}
      {tool !== "cursor" && <div className="absolute inset-0 z-10 cursor-crosshair" onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp} />}
      {loading && <div className="absolute inset-0 z-30 flex items-center justify-center bg-slate-950/75 text-sm text-slate-300">Loading {symbol} {timeframe} data…</div>}
      {error && !loading && <div className="absolute inset-0 z-30 flex items-center justify-center"><div className="rounded border border-red-800 bg-red-950 p-6 text-center"><p className="font-semibold text-red-300">Unable to load chart</p><p className="mt-1 text-xs text-red-400">{error}</p><button onClick={() => void fetchBars()} className="mt-4 rounded bg-red-800 px-3 py-1.5 text-xs text-white">Retry</button></div></div>}
      {!loading && !error && !bars.length && <div className="absolute inset-0 z-20 flex items-center justify-center text-center text-slate-500"><div><div className="text-3xl">⌁</div><p className="mt-2">No {symbol} {timeframe} bars found</p><p className="text-xs">Adjust the selected session or date range.</p></div></div>}
    </div>
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-slate-800 bg-slate-900/70 px-4 py-2 text-[11px] text-slate-400"><span><b className="text-slate-200">{formatBarCount(bars.length)}</b> bars</span><span><b className="text-slate-200">{symbol}</b> {TIMEFRAMES.find((item) => item.value === timeframe)?.label}</span>{first && last && <span>{new Date(first.timestamp).toLocaleDateString()} — {new Date(last.timestamp).toLocaleDateString()}</span>}<span className="ml-auto flex flex-wrap gap-3"><span className="text-sky-300">EMA 9</span><span className="text-orange-300">EMA 21</span><span className="text-purple-300">EMA 50</span><span className="text-red-300">EMA 200</span><span className="text-amber-300">VWAP</span><span className="text-cyan-300">SMT</span></span></div>
  </div>;
}
