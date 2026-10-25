import { Lock, Plus, Search, Users } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import LandscapeArt from "../components/LandscapeArt";
import { Empty, ErrorNote, Field, Modal, Spinner, Tabs } from "../components/ui";
import { api, results } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useApi } from "../lib/hooks";
import { GROUP_CATEGORIES, label } from "../lib/format";

function CreateGroup({ onClose }) {
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", description: "", category: "general", privacy_type: "public" });
  const [error, setError] = useState(null);
  const submit = async (e) => {
    e.preventDefault();
    try { const g = await api("/groups/", { method: "POST", body: form }); navigate(`/groups/${g.id}`); }
    catch (err) { setError(err); }
  };
  return (
    <Modal title="Create a group" onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <Field label="Group name" required><input className="input" required maxLength={150} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
        <Field label="What's the group about?"><textarea className="input" rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
        <Field label="Category"><select className="input" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
          {GROUP_CATEGORIES.map((c) => <option key={c} value={c}>{label(c)}</option>)}</select></Field>
        <fieldset><legend className="label">Who can join?</legend>
          {[["public", "Anyone can join"], ["private", "Only people an admin adds (private)"]].map(([v, t]) => (
            <label key={v} className="flex items-center gap-2 py-1 text-sm"><input type="radio" className="accent-forest-700" checked={form.privacy_type === v}
              onChange={() => setForm({ ...form, privacy_type: v })} /> {t}</label>
          ))}
        </fieldset>
        <ErrorNote error={error} />
        <button className="btn-primary w-full">Create group</button>
      </form>
    </Modal>
  );
}

export function GroupCard({ g }) {
  return (
    <Link to={`/groups/${g.id}`} className="card flex overflow-hidden transition-colors hover:border-forest-500">
      <LandscapeArt seed={g.id * 7} tent={false} className="h-auto w-28 shrink-0" />
      <div className="min-w-0 p-4">
        <p className="flex items-center gap-2 font-bold text-navy-900">{g.name} {g.privacy_type === "private" && <Lock size={14} className="text-ink/50" aria-label="Private" />}</p>
        <p className="text-xs text-ink/60">{label(g.category)} · {g.member_count} member{g.member_count === 1 ? "" : "s"}</p>
        {g.description && <p className="mt-1 line-clamp-2 text-sm text-ink/75">{g.description}</p>}
        {g.my_role && <p className="mt-2 text-xs font-semibold text-forest-700">You're a {g.my_role === "co_admin" ? "co-admin" : g.my_role}</p>}
      </div>
    </Link>
  );
}

export default function Groups() {
  const { user } = useAuth();
  const [tab, setTab] = useState("all");
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [creating, setCreating] = useState(false);
  const all = useApi(tab === "all" ? `/groups/?page_size=50&search=${encodeURIComponent(search)}` : null);
  const mine = useApi(tab === "mine" ? "/groups/mine/" : null);
  const groups = tab === "all" ? results(all.data) : results(mine.data);
  const loading = tab === "all" ? all.loading : mine.loading;
  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <h1 className="mr-auto text-2xl font-extrabold">Groups</h1>
        <form onSubmit={(e) => { e.preventDefault(); setSearch(q); setTab("all"); }} className="relative w-full sm:w-64">
          <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink/45" />
          <input className="input pl-10" placeholder="Search groups…" aria-label="Search groups" value={q} onChange={(e) => setQ(e.target.value)} />
        </form>
        {user && <button className="btn-primary" onClick={() => setCreating(true)}><Plus size={16} /> Create a group</button>}
      </div>
      <Tabs active={tab} onChange={setTab} tabs={[["all", "All groups"], ...(user ? [["mine", "My groups"]] : [])]} />
      <div className="mt-5">
        {loading && <Spinner />}
        {!loading && groups.length === 0 && <Empty title={tab === "mine" ? "You haven't joined any groups yet" : "No groups found"} />}
        <div className="grid gap-4 md:grid-cols-2">{groups.map((g) => <GroupCard key={g.id} g={g} />)}</div>
      </div>
      {creating && <CreateGroup onClose={() => setCreating(false)} />}
    </div>
  );
}
