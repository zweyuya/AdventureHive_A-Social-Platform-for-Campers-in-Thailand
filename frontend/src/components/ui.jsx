import { Star, X } from "lucide-react";
import { useEffect } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { label } from "../lib/format";

const AVATAR_COLOURS = ["bg-forest-600", "bg-sunrise-500", "bg-navy-700", "bg-teal-600", "bg-amber-600", "bg-emerald-700"];

export function Avatar({ name = "?", id = 0, src, size = "h-9 w-9 text-sm", className = "" }) {
  if (src)
    return <img src={src} alt="" title={name} className={`inline-block shrink-0 rounded-full object-cover ring-2 ring-white ${size} ${className}`} />;
  const initials = name.split(/\s+/).map((p) => p[0]).join("").slice(0, 2).toUpperCase();
  return (
    <span className={`inline-flex shrink-0 items-center justify-center rounded-full font-bold text-white ring-2 ring-white ${AVATAR_COLOURS[id % AVATAR_COLOURS.length]} ${size} ${className}`}
          title={name} aria-hidden="true">
      {initials}
    </span>
  );
}

export function Stars({ value, size = 16 }) {
  const v = Number(value) || 0;
  return (
    <span className="inline-flex" aria-label={`${v.toFixed(1)} out of 5 stars`}>
      {[1, 2, 3, 4, 5].map((i) => (
        <Star key={i} size={size} className={i <= Math.round(v) ? "fill-sunrise-500 text-sunrise-500" : "text-slate-300"} />
      ))}
    </span>
  );
}

export function StarPicker({ value, onChange }) {
  return (
    <div className="flex gap-1" role="radiogroup" aria-label="Rating">
      {[1, 2, 3, 4, 5].map((i) => (
        <button key={i} type="button" role="radio" aria-checked={value === i} aria-label={`${i} star${i > 1 ? "s" : ""}`}
                onClick={() => onChange(i)} className="rounded p-0.5">
          <Star size={28} className={i <= value ? "fill-sunrise-500 text-sunrise-500" : "text-slate-300"} />
        </button>
      ))}
    </div>
  );
}

const BADGE = {
  published: "bg-forest-100 text-forest-800", open: "bg-forest-100 text-forest-800",
  full: "bg-sunrise-100 text-sunrise-600", draft: "bg-slate-100 text-slate-700",
  cancelled: "bg-red-100 text-red-700", completed: "bg-navy-700/10 text-navy-800",
  pending_review: "bg-amber-100 text-amber-800", rejected: "bg-red-100 text-red-700",
  archived: "bg-slate-100 text-slate-600", confirmed: "bg-forest-100 text-forest-800",
  waitlisted: "bg-sunrise-100 text-sunrise-600", attended: "bg-forest-100 text-forest-800",
  no_show: "bg-slate-100 text-slate-700", answered: "bg-forest-100 text-forest-800",
  closed: "bg-slate-100 text-slate-700", hidden: "bg-red-100 text-red-700",
};
const BADGE_TEXT = { published: "Open", pending_review: "Pending review", no_show: "No-show" };

export function StatusBadge({ status, className = "" }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${BADGE[status] || "bg-slate-100 text-slate-700"} ${className}`}>
      {BADGE_TEXT[status] || label(status)}
    </span>
  );
}

export function Spinner({ text = "Loading…" }) {
  return (
    <div className="flex items-center justify-center gap-3 py-16 text-ink/60" role="status">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-forest-600 border-t-transparent" />
      {text}
    </div>
  );
}

export function ErrorNote({ error, className = "" }) {
  if (!error) return null;
  return (
    <p className={`rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 ${className}`} role="alert">
      {typeof error === "string" ? error : error.message}
    </p>
  );
}

export function Empty({ title, children, action }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 bg-white/60 px-6 py-10 text-center">
      <p className="font-semibold text-navy-900">{title}</p>
      {children && <p className="mt-1 text-sm text-ink/60">{children}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function Modal({ title, onClose, children, wide = false }) {
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-[1000] flex items-end justify-center bg-navy-900/40 p-4 sm:items-center" onMouseDown={onClose}>
      <div role="dialog" aria-modal="true" aria-label={title}
           className={`card max-h-[90vh] w-full overflow-y-auto p-6 ${wide ? "max-w-2xl" : "max-w-lg"}`}
           onMouseDown={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-start justify-between gap-4">
          <h2 className="text-lg font-bold">{title}</h2>
          <button onClick={onClose} className="btn-ghost -m-2 p-2" aria-label="Close"><X size={18} /></button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Field({ label: text, error, children, hint, required }) {
  return (
    <label className="block">
      <span className="label">{text}{required && <span className="text-red-600"> *</span>}</span>
      {children}
      {hint && !error && <span className="mt-1 block text-xs text-ink/55">{hint}</span>}
      {error && <span className="mt-1 block text-xs text-red-700">{error}</span>}
    </label>
  );
}

export function Tabs({ tabs, active, onChange }) {
  return (
    <div className="flex gap-1 overflow-x-auto border-b border-slate-200" role="tablist">
      {tabs.map(([key, text]) => (
        <button key={key} role="tab" aria-selected={active === key} onClick={() => onChange(key)}
                className={`-mb-px whitespace-nowrap border-b-2 px-4 py-2.5 text-sm font-semibold transition-colors ${
                  active === key ? "border-forest-700 text-forest-800" : "border-transparent text-ink/60 hover:text-forest-800"}`}>
          {text}
        </button>
      ))}
    </div>
  );
}

export function RequireAuth({ children }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <Spinner />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return children;
}

export function SectionHead({ title, action }) {
  return (
    <div className="mb-3 flex items-baseline justify-between gap-4">
      <h2 className="text-lg font-bold">{title}</h2>
      {action}
    </div>
  );
}
