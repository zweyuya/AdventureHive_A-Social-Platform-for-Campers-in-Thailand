/**
 * Generated landscape illustrations in the style of the logo (sun, layered
 * mountains, a tent). Used instead of stock photos, so every campsite and trip
 * has a consistent, licence-free image. The same seed always gives the same picture.
 */
function rng(seed) {
  let a = (seed * 2654435761) >>> 0 || 1;
  return () => {
    a |= 0; a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const MOODS = {
  dawn: { sky: ["#ffd9a8", "#ffb27a", "#f7c9a0"], sun: "#f58a1f", hills: ["#7fb79a", "#3f9a6f", "#178a5e", "#0f6647"], water: "#f6c79c" },
  day: { sky: ["#bfe3f0", "#dff1f2", "#f3f8f2"], sun: "#fba64a", hills: ["#9fcdb4", "#5aa983", "#1f8a5f", "#0b4f37"], water: "#9fd0dc" },
  dusk: { sky: ["#f2a46b", "#e9765a", "#b65a6e"], sun: "#ffd27a", hills: ["#8b6d8a", "#4f6b6a", "#1f5143", "#0b3a2b"], water: "#d98a6e" },
  night: { sky: ["#0e1c44", "#1b3270", "#2b4a7a"], sun: "#f4efd8", hills: ["#2a4a6a", "#1d3f4f", "#123a33", "#082a21"], water: "#25406a" },
};

function ridge(r, baseY, amp, peaks) {
  const pts = [[0, 240], [0, baseY]];
  for (let i = 1; i <= peaks; i++) {
    const x = (400 / peaks) * i - (400 / peaks) * r() * 0.6;
    pts.push([x - 20, baseY - amp * (0.35 + r() * 0.65)]);
    pts.push([x + 15, baseY - amp * r() * 0.25]);
  }
  pts.push([400, baseY - amp * r() * 0.4], [400, 240]);
  return pts.map((p) => p.map((n) => n.toFixed(1)).join(",")).join(" ");
}

export default function LandscapeArt({ seed = 1, mood, className = "", tent = true, label }) {
  const r = rng(seed + 7);
  const m = MOODS[mood || ["dawn", "day", "dusk", "night"][Math.floor(rng(seed * 13 + 5)() * 4)]];
  const id = `sky${seed}${mood || ""}`;
  const sunX = 60 + r() * 280, sunY = 55 + r() * 35;
  const stars = m === MOODS.night ? Array.from({ length: 40 }, () => [r() * 400, r() * 120, r() * 1.2 + 0.3]) : [];
  const lake = r() > 0.55;
  const tentX = 90 + r() * 220;
  return (
    <svg viewBox="0 0 400 240" preserveAspectRatio="xMidYMid slice" className={className}
         role={label ? "img" : undefined} aria-label={label} aria-hidden={label ? undefined : true}>
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={m.sky[0]} /><stop offset="0.6" stopColor={m.sky[1]} /><stop offset="1" stopColor={m.sky[2]} />
        </linearGradient>
      </defs>
      <rect width="400" height="240" fill={`url(#${id})`} />
      {stars.map(([x, y, s], i) => <circle key={i} cx={x} cy={y} r={s} fill="#fff" opacity={0.4 + s / 3} />)}
      <circle cx={sunX} cy={sunY} r={m === MOODS.night ? 14 : 26} fill={m.sun} opacity={0.95} />
      <polygon points={ridge(r, 150, 90, 3)} fill={m.hills[0]} />
      <polygon points={ridge(r, 175, 80, 4)} fill={m.hills[1]} />
      {lake && <ellipse cx={200 + (r() - 0.5) * 120} cy="205" rx="150" ry="16" fill={m.water} opacity="0.85" />}
      <polygon points={ridge(r, 205, 55, 5)} fill={m.hills[2]} />
      <path d={`M0 205 Q 120 ${192 + r() * 8} 240 200 T 400 196 V240 H0Z`} fill={m.hills[3]} />
      {tent && (
        <g transform={`translate(${tentX} 172)`}>
          <polygon points="0,26 20,0 40,26" fill="#f58a1f" />
          <polygon points="20,0 40,26 30,26" fill="#e5711a" />
          <polygon points="17,26 20,12 23,26" fill="#5b2a0c" />
        </g>
      )}
    </svg>
  );
}
