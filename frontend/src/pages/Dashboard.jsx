import { ChevronRight, HelpCircle, Map, PlusCircle, Search, Tent, Users } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { CampsiteRow, TripCard } from "../components/cards";
import CampsiteImage from "../components/CampsiteImage";
import HeroSlideshow from "../components/HeroSlideshow";
import LandscapeArt from "../components/LandscapeArt";
import { Avatar, Empty, SectionHead, Spinner, Stars } from "../components/ui";
import { results } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useApi } from "../lib/hooks";
import { timeAgo } from "../lib/format";

function Hero() {
  const [q, setQ] = useState("");
  const navigate = useNavigate();
  return (
    <HeroSlideshow>
        <h1 className="max-w-lg text-3xl font-extrabold leading-tight !text-white sm:text-4xl">Find your next camping adventure</h1>
        <p className="mt-2 max-w-md text-white/85">Campsites, trips and people across Thailand.</p>
        <form onSubmit={(e) => { e.preventDefault(); navigate(`/campsites?search=${encodeURIComponent(q)}`); }}
              className="mt-6 flex max-w-lg items-center gap-2 rounded-xl bg-white p-1.5 shadow-card">
          <Search size={20} className="ml-2 text-ink/45" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search campsites or provinces…"
                 aria-label="Search campsites" className="min-w-0 flex-1 bg-transparent px-1 py-2 text-sm outline-none" />
          <button className="btn-primary">Search</button>
        </form>
    </HeroSlideshow>
  );
}

function MyGroups() {
  const { user } = useAuth();
  const { data, loading } = useApi(user ? "/groups/mine/" : null);
  return (
    <section className="card p-4">
      <SectionHead title="My groups" action={<Link to="/groups" className="link text-sm">View all</Link>} />
      {!user && <p className="text-sm text-ink/60"><Link to="/login" className="link">Log in</Link> to see your groups.</p>}
      {loading && <Spinner />}
      {user && data?.length === 0 && <p className="text-sm text-ink/60">You haven't joined a group yet. <Link to="/groups" className="link">Find one</Link>.</p>}
      <ul className="-mx-2">
        {(data || []).slice(0, 4).map((g) => (
          <li key={g.id}>
            <Link to={`/groups/${g.id}`} className="flex items-center gap-3 rounded-lg p-2 hover:bg-forest-50">
              <LandscapeArt seed={g.id * 7} tent={false} className="h-11 w-11 shrink-0 rounded-full" />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-semibold text-navy-900">{g.name}</span>
                <span className="text-xs text-ink/60">{g.member_count} member{g.member_count === 1 ? "" : "s"}</span>
              </span>
              <ChevronRight size={18} className="text-ink/40" />
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

function QuickLinks() {
  const links = [[PlusCircle, "Create a trip", "/trips/new"], [Map, "Explore the map", "/campsites"],
                 [Users, "Find groups", "/groups"], [Tent, "Suggest a campsite", "/campsites/new"], [HelpCircle, "Ask the community", "/questions"]];
  return (
    <section className="card p-4">
      <SectionHead title="Quick links" />
      <ul className="space-y-2">
        {links.map(([Icon, text, to]) => (
          <li key={to}>
            <Link to={to} className="flex items-center gap-3 rounded-lg border border-slate-200 px-3 py-2.5 text-sm font-medium hover:border-forest-600 hover:bg-forest-50">
              <Icon size={18} className="text-forest-700" /> {text}
              <ChevronRight size={16} className="ml-auto text-ink/40" />
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

function RecentReviews() {
  const { data, loading } = useApi("/reviews/?page_size=3");
  const items = results(data).slice(0, 3);
  return (
    <section>
      <SectionHead title="Recent reviews from verified campers" />
      {loading && <Spinner />}
      {!loading && items.length === 0 && <Empty title="No reviews yet">Reviews appear after trips are completed and attendance is recorded.</Empty>}
      <div className="grid gap-4 md:grid-cols-3">
        {items.map((r) => (
          <article key={r.id} className="card flex flex-col overflow-hidden">
            <CampsiteImage src={r.campsite_image} seed={r.campsite_id} className="h-28 w-full" />
            <div className="flex flex-1 flex-col p-4">
              <div className="flex items-center gap-2">
                <Avatar name={r.author.display_name} id={r.author.id} src={r.author.avatar} size="h-8 w-8 text-xs" />
                <span className="text-sm"><span className="font-semibold">{r.author.display_name}</span>
                  <span className="block text-xs text-ink/55">{timeAgo(r.created_at)}</span></span>
              </div>
              <Stars value={r.rating} size={14} />
              <p className="mt-2 line-clamp-3 text-sm text-ink/80">“{r.review_text || "No written review."}”</p>
              <Link to={`/campsites/${r.campsite_id}`} className="link mt-auto pt-3 text-sm">{r.campsite_name}</Link>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

export default function Dashboard() {
  const trips = useApi("/trips/?page_size=3");
  const top = useApi("/campsites/?ordering=-review_count&page_size=4");
  return (
    <div className="mx-auto grid max-w-7xl gap-6 px-4 py-6 lg:grid-cols-[1fr_320px]">
      <div className="min-w-0 space-y-8">
        <Hero />
        <section>
          <SectionHead title="Upcoming camping trips" action={<Link to="/trips" className="link text-sm">View all</Link>} />
          {trips.loading && <Spinner />}
          {!trips.loading && results(trips.data).length === 0 &&
            <Empty title="No upcoming trips yet" action={<Link to="/trips/new" className="btn-primary">Create the first trip</Link>} />}
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {results(trips.data).slice(0, 3).map((t) => <TripCard key={t.id} trip={t} />)}
          </div>
        </section>
        <RecentReviews />
      </div>
      <aside className="space-y-6">
        <MyGroups />
        <QuickLinks />
        <section className="card p-4">
          <SectionHead title="Popular campsites" action={<Link to="/campsites" className="link text-sm">Map</Link>} />
          <div className="-mx-2">{results(top.data).map((c) => <CampsiteRow key={c.id} c={c} />)}</div>
        </section>
      </aside>
    </div>
  );
}

