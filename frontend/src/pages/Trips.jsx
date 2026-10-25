import { Plus } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";
import { TripCard } from "../components/cards";
import { Empty, Spinner, Tabs } from "../components/ui";
import { results } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useApi } from "../lib/hooks";
import { DIFFICULTIES, PROVINCES, label } from "../lib/format";

export default function Trips() {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") || "upcoming";
  const f = Object.fromEntries(["province", "difficulty", "has_spots", "location", "search"].map((k) => [k, params.get(k) || ""]));
  const query = new URLSearchParams(Object.entries(f).filter(([, v]) => v)).toString();
  const upcoming = useApi(tab === "upcoming" ? `/trips/?page_size=50&${query}` : null, [query]);
  const mine = useApi(tab === "mine" && user ? "/trips/mine/" : null);
  const set = (k, v) => { const next = new URLSearchParams(params); v ? next.set(k, v) : next.delete(k); setParams(next); };
  const trips = tab === "mine" ? results(mine.data) : results(upcoming.data);
  const loading = tab === "mine" ? mine.loading : upcoming.loading;

  return (
    <div className="mx-auto max-w-7xl px-4 py-6">
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <h1 className="mr-auto text-2xl font-extrabold">Camping trips</h1>
        <Link to="/trips/new" className="btn-primary"><Plus size={16} /> Create a trip</Link>
      </div>
      <Tabs active={tab} onChange={(t) => set("tab", t === "upcoming" ? "" : t)}
            tabs={[["upcoming", "Upcoming trips"], ...(user ? [["mine", "My trips"]] : [])]} />
      {tab === "upcoming" && (
        <div className="my-4 flex flex-wrap gap-3">
          <select className="input w-auto" value={f.province} onChange={(e) => set("province", e.target.value)} aria-label="Province">
            <option value="">All provinces</option>{PROVINCES.map((p) => <option key={p}>{p}</option>)}
          </select>
          <select className="input w-auto" value={f.difficulty} onChange={(e) => set("difficulty", e.target.value)} aria-label="Difficulty">
            <option value="">Any difficulty</option>{DIFFICULTIES.map((d) => <option key={d} value={d}>{label(d)}</option>)}
          </select>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="h-4 w-4 accent-forest-700" checked={f.has_spots === "true"} onChange={(e) => set("has_spots", e.target.checked ? "true" : "")} />
            Only trips with free spots
          </label>
          {f.location && <button className="chip chip-on" onClick={() => set("location", "")}>One campsite only ✕</button>}
        </div>
      )}
      <div className="mt-4">
        {loading && <Spinner />}
        {!loading && trips.length === 0 && (
          <Empty title={tab === "mine" ? "You haven't joined or organised any trips yet" : "No trips match"}
                 action={<Link to="/trips/new" className="btn-primary">Create a trip</Link>} />
        )}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">{trips.map((t) => <TripCard key={t.id} trip={t} />)}</div>
      </div>
    </div>
  );
}
