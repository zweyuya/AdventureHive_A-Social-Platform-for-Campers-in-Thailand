import { List, Map as MapIcon, Plus, Search, SlidersHorizontal } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { CampsiteRow } from "../components/cards";
import { CampsiteMap } from "../components/maps";
import { Empty, Spinner } from "../components/ui";
import { results } from "../lib/api";
import { useApi } from "../lib/hooks";
import { CAMPSITE_CATEGORIES, PROVINCES, label } from "../lib/format";

const FACILITIES = [["has_water_source", "Water source"], ["has_restrooms", "Restrooms"], ["fire_pit_allowed", "Fire pit allowed"]];

function Filters({ draft, setDraft, onApply, onClear }) {
  const toggle = (k) => setDraft({ ...draft, [k]: draft[k] ? "" : "true" });
  return (
    <form onSubmit={(e) => { e.preventDefault(); onApply(); }} className="space-y-5">
      <label className="block"><span className="label">Province</span>
        <select className="input" value={draft.province} onChange={(e) => setDraft({ ...draft, province: e.target.value })}>
          <option value="">All provinces</option>
          {PROVINCES.map((p) => <option key={p}>{p}</option>)}
        </select>
      </label>
      <label className="block"><span className="label">Category</span>
        <select className="input" value={draft.category} onChange={(e) => setDraft({ ...draft, category: e.target.value })}>
          <option value="">All categories</option>
          {CAMPSITE_CATEGORIES.map((c) => <option key={c} value={c}>{label(c)}</option>)}
        </select>
      </label>
      <fieldset>
        <legend className="label">Facilities</legend>
        {FACILITIES.map(([k, text]) => (
          <label key={k} className="flex items-center gap-2 py-1 text-sm">
            <input type="checkbox" className="h-4 w-4 accent-forest-700" checked={!!draft[k]} onChange={() => toggle(k)} /> {text}
          </label>
        ))}
        <label className="flex items-center gap-2 py-1 text-sm">
          <input type="checkbox" className="h-4 w-4 accent-forest-700" checked={draft.permit_status === "required"}
                 onChange={() => setDraft({ ...draft, permit_status: draft.permit_status ? "" : "required" })} /> Permit required
        </label>
      </fieldset>
      <label className="block"><span className="label">Minimum rating: {draft.min_rating || "any"}</span>
        <input type="range" min="0" max="5" step="1" value={draft.min_rating || 0} className="w-full accent-forest-700"
               onChange={(e) => setDraft({ ...draft, min_rating: e.target.value === "0" ? "" : e.target.value })} />
      </label>
      <button className="btn-primary w-full">Apply filters</button>
      <button type="button" onClick={onClear} className="btn-ghost w-full">Clear filters</button>
    </form>
  );
}

const KEYS = ["search", "province", "category", "has_water_source", "has_restrooms", "fire_pit_allowed", "permit_status", "min_rating"];

export default function Campsites() {
  const [params, setParams] = useSearchParams();
  const applied = Object.fromEntries(KEYS.map((k) => [k, params.get(k) || ""]));
  const [draft, setDraft] = useState(applied);
  const [view, setView] = useState("map");
  const [showFilters, setShowFilters] = useState(false);
  const query = useMemo(() => new URLSearchParams(Object.entries(applied).filter(([, v]) => v)).toString(), [params]); // eslint-disable-line
  const geo = useApi(`/map/campsites/?${query}`);
  const list = useApi(`/campsites/?page_size=100&${query}`);
  const apply = (next = draft) => { setParams(Object.fromEntries(Object.entries(next).filter(([, v]) => v))); setShowFilters(false); };
  const features = geo.data?.features || [];

  return (
    <div className="mx-auto max-w-7xl px-4 py-6">
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <h1 className="mr-auto text-2xl font-extrabold">Campsites</h1>
        <form onSubmit={(e) => { e.preventDefault(); apply(); }} className="relative w-full sm:w-72">
          <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink/45" />
          <input className="input pl-10" placeholder="Search campsites…" aria-label="Search campsites"
                 value={draft.search} onChange={(e) => setDraft({ ...draft, search: e.target.value })} />
        </form>
        <div className="flex rounded-lg border border-slate-300 bg-white p-1" role="group" aria-label="View">
          {[["map", MapIcon, "Map"], ["list", List, "List"]].map(([v, Icon, text]) => (
            <button key={v} onClick={() => setView(v)} aria-pressed={view === v}
                    className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-semibold ${view === v ? "bg-forest-700 text-white" : "text-ink/70"}`}>
              <Icon size={16} /> {text}
            </button>
          ))}
        </div>
        <button className="btn-outline lg:hidden" onClick={() => setShowFilters((s) => !s)}><SlidersHorizontal size={16} /> Filters</button>
        <Link to="/campsites/new" className="btn-primary"><Plus size={16} /> Suggest a campsite</Link>
      </div>

      <div className="grid gap-6 lg:grid-cols-[260px_1fr]">
        <aside className={`card h-fit p-5 ${showFilters ? "" : "hidden lg:block"}`}>
          <h2 className="mb-4 font-bold">Filters</h2>
          <Filters draft={draft} setDraft={setDraft} onApply={() => apply()} onClear={() => { const empty = Object.fromEntries(KEYS.map((k) => [k, ""])); setDraft(empty); apply(empty); }} />
        </aside>
        <section aria-live="polite">
          <p className="mb-2 text-sm text-ink/60">{features.length} campsite{features.length === 1 ? "" : "s"} found</p>
          {view === "map" ? (
            <div className="card h-[560px] overflow-hidden">
              {geo.loading ? <Spinner /> : <CampsiteMap features={features} className="h-full w-full" />}
            </div>
          ) : (
            <div className="card divide-y divide-slate-100 p-2">
              {list.loading && <Spinner />}
              {!list.loading && results(list.data).length === 0 && <Empty title="No campsites match these filters">Try removing a filter.</Empty>}
              {results(list.data).map((c) => <CampsiteRow key={c.id} c={c} />)}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
