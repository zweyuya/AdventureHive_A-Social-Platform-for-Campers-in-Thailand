import { Plus } from "lucide-react";
import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { Empty, ErrorNote, Spinner, StatusBadge } from "../components/ui";
import { api } from "../lib/api";
import { useApi } from "../lib/hooks";
import { fmtDate } from "../lib/format";

export default function MySubmissions() {
  const { state } = useLocation();
  const { data, loading, reload } = useApi("/campsites/mine/");
  const [error, setError] = useState(null);
  const submit = async (id) => { setError(null); try { await api(`/campsites/${id}/submit/`, { method: "POST" }); reload(); } catch (e) { setError(e); } };
  return (
    <div className="mx-auto max-w-4xl px-4 py-6">
      <div className="mb-4 flex items-center gap-3">
        <h1 className="mr-auto text-2xl font-extrabold">My campsite submissions</h1>
        <Link to="/campsites/new" className="btn-primary"><Plus size={16} /> Suggest a campsite</Link>
      </div>
      {state?.flash && <p className="mb-4 rounded-lg bg-forest-50 p-3 text-sm text-forest-800">{state.flash}</p>}
      <ErrorNote error={error} className="mb-4" />
      {loading && <Spinner />}
      {!loading && (data || []).length === 0 && <Empty title="You haven't suggested any campsites yet" />}
      <ul className="space-y-3">
        {(data || []).map((c) => (
          <li key={c.id} className="card p-4">
            <div className="flex flex-wrap items-center gap-3">
              <span className="mr-auto"><span className="font-semibold text-navy-900">{c.name}</span>
                <span className="block text-xs text-ink/55">{c.province} · updated {fmtDate(c.updated_at)}</span></span>
              <StatusBadge status={c.status} />
              {c.status === "published" && <Link to={`/campsites/${c.id}`} className="btn-outline btn-sm">View</Link>}
              {["draft", "rejected"].includes(c.status) && <>
                <Link to={`/campsites/${c.id}/edit`} className="btn-outline btn-sm">Edit</Link>
                <button className="btn-primary btn-sm" onClick={() => submit(c.id)}>{c.status === "rejected" ? "Resubmit" : "Send for review"}</button>
              </>}
            </div>
            {c.status === "pending_review" && <p className="mt-2 text-sm text-ink/60">Waiting for a moderator.</p>}
            {c.moderation_note && <p className="mt-2 rounded-lg bg-amber-50 p-3 text-sm text-amber-900"><span className="font-semibold">Moderator note:</span> {c.moderation_note}</p>}
          </li>
        ))}
      </ul>
    </div>
  );
}
