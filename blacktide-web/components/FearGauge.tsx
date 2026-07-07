export default function FearGauge({ value }: { value: number }) {
  const v = Math.max(0, Math.min(100, Math.round(value)));
  const len = Math.PI * 34;
  const pct = v / 100;
  const color = v < 45 ? "#f43f5e" : v > 55 ? "#10b981" : "#00D4FF";
  return (
    <svg viewBox="0 0 80 46" className="w-[72px] shrink-0">
      <path d="M6 42 A34 34 0 0 1 74 42" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="7" strokeLinecap="round" />
      <path d="M6 42 A34 34 0 0 1 74 42" fill="none" stroke={color} strokeWidth="7" strokeLinecap="round" strokeDasharray={`${len * pct} ${len}`} />
      <text x="40" y="40" textAnchor="middle" fill={color} fontSize="15" fontWeight="700" fontFamily="ui-monospace">{v}</text>
    </svg>
  );
}
