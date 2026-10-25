const dShort = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short" });
const dLong = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", year: "numeric" });
const tShort = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit" });

export function dateRange(start, end) {
  const s = new Date(start), e = new Date(end);
  if (s.getFullYear() === e.getFullYear() && s.getMonth() === e.getMonth())
    return s.getDate() === e.getDate() ? dLong.format(s) : `${s.getDate()} – ${dLong.format(e)}`;
  return `${dShort.format(s)} – ${dLong.format(e)}`;
}
export const fmtDate = (d) => (d ? dLong.format(new Date(d)) : "");
export const fmtTime = (d) => (d ? tShort.format(new Date(d)) : "");

export function timeAgo(d) {
  const s = (Date.now() - new Date(d).getTime()) / 1000;
  if (s < 60) return "just now";
  const units = [["year", 31536000], ["month", 2592000], ["week", 604800], ["day", 86400], ["hour", 3600], ["minute", 60]];
  for (const [name, secs] of units) {
    const n = Math.floor(s / secs);
    if (n >= 1) return `${n} ${name}${n > 1 ? "s" : ""} ago`;
  }
  return "";
}

export const label = (v) => (v ? String(v).replaceAll("_", " ").replace(/^\w/, (c) => c.toUpperCase()) : "");

export const PROVINCES = [
  "Chiang Mai", "Chiang Rai", "Kanchanaburi", "Loei", "Mae Hong Son", "Nakhon Ratchasima",
  "Nan", "Phang Nga", "Phetchaburi", "Prachuap Khiri Khan", "Satun", "Ubon Ratchathani",
];
export const LEVELS = ["beginner", "intermediate", "advanced", "expert"];
export const DIFFICULTIES = ["easy", "moderate", "difficult", "strenuous"];
export const CAMPSITE_CATEGORIES = ["campsite", "campground", "backcountry", "other"];
export const GROUP_CATEGORIES = ["car_camping", "backpacking", "family_camping", "van_life", "general"];
