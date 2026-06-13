export default function Sparkline({ data, width = 96, height = 34, up }: { data: number[]; width?: number; height?: number; up?: boolean }) {
  if (!data.length) return null;
  const min = Math.min(...data), max = Math.max(...data);
  const span = max - min || 1;
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * width},${height - ((v - min) / span) * (height - 4) - 2}`);
  const line = pts.join(" ");
  const area = `M0,${height} L${pts.join(" L")} L${width},${height} Z`;
  const c = up ? "#10b981" : "#f43f5e";
  return (
    <svg width={width} height={height} className="shrink-0 overflow-visible">
      <path d={area} fill={c} opacity={0.08} />
      <polyline points={line} fill="none" stroke={c} strokeWidth={1.5} />
    </svg>
  );
}
