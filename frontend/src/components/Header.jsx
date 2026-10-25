import { Bell, LogOut, Menu, Plus, Tent, User, X, FileText, Star } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link, NavLink, useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { timeAgo } from "../lib/format";
import Logo from "./Logo";
import { Avatar } from "./ui";

const NAV = [["/", "Home"], ["/trips", "Trips"], ["/campsites", "Campsites"], ["/feed", "Feed"], ["/groups", "Groups"], ["/questions", "Q&A"]];

function useClickOutside(ref, onOutside) {
  useEffect(() => {
    const h = (e) => ref.current && !ref.current.contains(e.target) && onOutside();
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, [ref, onOutside]);
}

function NotificationBell() {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState({ unread_count: 0, results: [] });
  const ref = useRef(null);
  const navigate = useNavigate();
  useClickOutside(ref, () => setOpen(false));
  const load = () => api("/notifications/").then(setData).catch(() => {});
  useEffect(() => { load(); const t = setInterval(load, 60000); return () => clearInterval(t); }, []);

  const toggle = async () => {
    setOpen((o) => !o);
    if (!open && data.unread_count) {
      await api("/notifications/read-all/", { method: "POST" }).catch(() => {});
      setTimeout(load, 1500);
    }
  };
  return (
    <div className="relative" ref={ref}>
      <button onClick={toggle} className="btn-ghost relative p-2" aria-label={`Notifications (${data.unread_count} unread)`}>
        <Bell size={22} />
        {data.unread_count > 0 && (
          <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-sunrise-500 px-1 text-[10px] font-bold text-white">
            {data.unread_count}
          </span>
        )}
      </button>
      {open && (
        <div className="card absolute right-0 z-[900] mt-2 w-80 overflow-hidden">
          <p className="border-b border-slate-100 px-4 py-3 text-sm font-bold text-navy-900">Notifications</p>
          <ul className="max-h-96 overflow-y-auto">
            {data.results.length === 0 && <li className="px-4 py-6 text-center text-sm text-ink/60">You're all caught up.</li>}
            {data.results.map((n) => (
              <li key={n.id}>
                <button onClick={() => { setOpen(false); n.link && navigate(n.link); }}
                        className={`block w-full px-4 py-3 text-left text-sm hover:bg-forest-50 ${n.is_read ? "" : "bg-sunrise-100/40"}`}>
                  {n.message}
                  <span className="mt-0.5 block text-xs text-ink/50">{timeAgo(n.created_at)}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function UserMenu({ user }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const { logout } = useAuth();
  const navigate = useNavigate();
  useClickOutside(ref, () => setOpen(false));
  const go = (to) => { setOpen(false); navigate(to); };
  const items = [
    [User, "My profile", "/profile"], [Tent, "My trips", "/trips?tab=mine"], [Plus, "Suggest a campsite", "/campsites/new"],
    [FileText, "My campsite submissions", "/my/submissions"], [Star, "My reviews", "/profile#reviews"],
  ];
  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen((o) => !o)} aria-label="Account menu" className="rounded-full">
        <Avatar name={user.display_name} id={user.id} src={user.avatar} size="h-10 w-10 text-sm" />
      </button>
      {open && (
        <div className="card absolute right-0 z-[900] mt-2 w-60 py-2">
          <p className="px-4 pb-2 text-sm font-semibold text-navy-900">{user.display_name}
            <span className="block text-xs font-normal text-ink/55">{user.email}</span></p>
          {items.map(([Icon, text, to]) => (
            <button key={to} onClick={() => go(to)} className="flex w-full items-center gap-3 px-4 py-2 text-sm hover:bg-forest-50">
              <Icon size={16} className="text-forest-700" /> {text}
            </button>
          ))}
          <hr className="my-2 border-slate-100" />
          <button onClick={async () => { await logout(); go("/login"); }}
                  className="flex w-full items-center gap-3 px-4 py-2 text-sm text-red-700 hover:bg-red-50">
            <LogOut size={16} /> Log out
          </button>
        </div>
      )}
    </div>
  );
}

export default function Header() {
  const { user } = useAuth();
  const [mobileOpen, setMobileOpen] = useState(false);
  const linkClass = ({ isActive }) =>
    `rounded-lg px-3 py-2 text-sm font-semibold transition-colors ${isActive ? "text-forest-800 bg-forest-50" : "text-ink/70 hover:text-forest-800"}`;
  return (
    <header className="sticky top-0 z-[800] border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-4 px-4">
        <Logo />
        <nav className="ml-6 hidden items-center gap-1 md:flex" aria-label="Main">
          {NAV.map(([to, text]) => <NavLink key={to} to={to} end={to === "/"} className={linkClass}>{text}</NavLink>)}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          {user ? (
            <>
              <NotificationBell />
              <UserMenu user={user} />
            </>
          ) : (
            <>
              <Link to="/login" className="btn-ghost">Log in</Link>
              <Link to="/register" className="btn-primary hidden sm:inline-flex">Sign up</Link>
            </>
          )}
          <button className="btn-ghost p-2 md:hidden" onClick={() => setMobileOpen((o) => !o)} aria-label="Menu">
            {mobileOpen ? <X size={22} /> : <Menu size={22} />}
          </button>
        </div>
      </div>
      {mobileOpen && (
        <nav className="flex flex-col gap-1 border-t border-slate-100 px-4 py-3 md:hidden" aria-label="Mobile">
          {NAV.map(([to, text]) => (
            <NavLink key={to} to={to} end={to === "/"} className={linkClass} onClick={() => setMobileOpen(false)}>{text}</NavLink>
          ))}
        </nav>
      )}
    </header>
  );
}
