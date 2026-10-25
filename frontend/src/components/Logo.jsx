import { Link } from "react-router-dom";

/** The AdventureHive mark + wordmark. `stacked` = centred version for auth pages. */
export default function Logo({ stacked = false, tagline = true, to = "/" }) {
  if (stacked)
    return (
      <Link to={to} className="flex flex-col items-center text-center" aria-label="AdventureHive home">
        <img src="/logo-mark.png" alt="" className="h-16 w-auto" />
        <span className="mt-2 text-3xl font-extrabold tracking-tight text-navy-800">AdventureHive</span>
        {tagline && <span className="text-sm text-ink/60">Discover, camp and connect in Thailand</span>}
      </Link>
    );
  return (
    <Link to={to} className="flex items-center gap-2.5" aria-label="AdventureHive home">
      <img src="/logo-mark.png" alt="" className="h-9 w-auto" />
      <span className="leading-tight">
        <span className="block text-xl font-extrabold tracking-tight text-navy-800">AdventureHive</span>
        {tagline && <span className="hidden text-[11px] text-ink/55 sm:block">Discover, camp and connect in Thailand</span>}
      </span>
    </Link>
  );
}
