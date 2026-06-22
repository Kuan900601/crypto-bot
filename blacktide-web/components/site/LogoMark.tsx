/** 動態波浪 Logo，向量繪製、各尺寸清晰、hover 加速。見 reference/landing-v8.jsx。 */
export default function LogoMark({ size = 42 }: { size?: number }) {
  return (
    <div className="logo-wrap" style={{ width: size, height: size }}>
      <div className="logo-ring" />
      <div className="logo-body">
        <div className="logo-current" />
        <div className="logo-sweep" />
        <div className="logo-inring" />
        <svg viewBox="0 0 48 48" style={{ position: "absolute", inset: 0, zIndex: 2 }}>
          <defs>
            <linearGradient id="lgWave" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#8A6E22" />
              <stop offset="45%" stopColor="#E8C66E" />
              <stop offset="55%" stopColor="#FFF6D6" />
              <stop offset="100%" stopColor="#C9A24B" />
            </linearGradient>
            <linearGradient id="lgWave2" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="#1B8A82" />
              <stop offset="50%" stopColor="#37D6C4" />
              <stop offset="100%" stopColor="#1B8A82" />
            </linearGradient>
          </defs>
          <path d="M10,19 Q17,13 24,19 T38,19" fill="none" stroke="url(#lgWave2)" strokeWidth="1.6" strokeLinecap="round" opacity="0.75" />
          <path d="M9,26 Q16.5,18 24,26 T39,26" fill="none" stroke="url(#lgWave)" strokeWidth="3.2" strokeLinecap="round" />
          <path d="M11,33 Q17.5,27 24,33 T37,33" fill="none" stroke="url(#lgWave)" strokeWidth="2.2" strokeLinecap="round" opacity="0.6" />
        </svg>
      </div>
    </div>
  );
}
