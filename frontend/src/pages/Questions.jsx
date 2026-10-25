import { ArrowLeft, Check, Search } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Avatar, Empty, ErrorNote, Spinner, StatusBadge, Tabs } from "../components/ui";
import { api, results } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useApi } from "../lib/hooks";
import { timeAgo } from "../lib/format";

export function QuestionList() {
  const { user } = useAuth();
  const [tab, setTab] = useState("all");
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [form, setForm] = useState({ title: "", body: "" });
  const [error, setError] = useState(null);
  const query = `${tab === "unanswered" ? "unanswered=true&" : ""}search=${encodeURIComponent(search)}`;
  const { data, loading, reload } = useApi(`/questions/?${query}`);
  const ask = async (e) => {
    e.preventDefault(); setError(null);
    try { await api("/questions/", { method: "POST", body: form }); setForm({ title: "", body: "" }); reload(); }
    catch (err) { setError(err); }
  };
  return (
    <div className="mx-auto grid max-w-6xl gap-6 px-4 py-6 lg:grid-cols-[1fr_320px]">
      <div className="min-w-0">
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <h1 className="mr-auto text-2xl font-extrabold">Questions and answers</h1>
          <form onSubmit={(e) => { e.preventDefault(); setSearch(q); }} className="relative w-full sm:w-64">
            <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-ink/45" />
            <input className="input pl-10" placeholder="Search questions…" aria-label="Search questions" value={q} onChange={(e) => setQ(e.target.value)} />
          </form>
        </div>
        <Tabs active={tab} onChange={setTab} tabs={[["all", "All"], ["unanswered", "Unanswered"]]} />
        {loading && <Spinner />}
        {!loading && results(data).length === 0 && <div className="mt-5"><Empty title="No questions here yet" /></div>}
        <ul className="divide-y divide-slate-100">
          {results(data).map((x) => (
            <li key={x.id} className="py-4">
              <Link to={`/questions/${x.id}`} className="font-semibold text-navy-900 hover:text-forest-800">{x.title}</Link>
              <p className="mt-1 flex flex-wrap items-center gap-2 text-xs text-ink/55">
                <StatusBadge status={x.status} />
                {x.answer_count} answer{x.answer_count === 1 ? "" : "s"}
                {x.campsite && <> · <Link className="link" to={`/campsites/${x.campsite.id}`}>{x.campsite.name}</Link></>}
                · {x.author.display_name}, {timeAgo(x.created_at)}
              </p>
            </li>
          ))}
        </ul>
      </div>
      <aside>
        {user ? (
          <form onSubmit={ask} className="card space-y-3 p-5">
            <h2 className="font-bold">Ask the community</h2>
            <p className="text-xs text-ink/60">For a question about one campsite, ask it on the campsite's page.</p>
            <input className="input" required maxLength={200} placeholder="Your question" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
            <textarea className="input" required rows={3} placeholder="Details" value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} />
            <ErrorNote error={error} />
            <button className="btn-primary w-full">Post question</button>
          </form>
        ) : <p className="card p-5 text-sm"><Link to="/login" className="link">Log in</Link> to ask a question.</p>}
      </aside>
    </div>
  );
}

export function QuestionDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const { data: q, loading, error, reload } = useApi(`/questions/${id}/`);
  const [answer, setAnswer] = useState("");
  const [err, setErr] = useState(null);
  if (loading && !q) return <Spinner />;
  if (error) return <div className="mx-auto max-w-3xl p-6"><ErrorNote error={error.status === 404 ? "This question doesn't exist or was hidden by a moderator." : error} /></div>;
  const run = async (fn) => { setErr(null); try { await fn(); reload(); } catch (e) { setErr(e); } };
  const isAsker = user && q.author.id === user.id;
  const open = ["open", "answered"].includes(q.status);
  return (
    <div className="mx-auto max-w-3xl px-4 py-6">
      <Link to={q.campsite ? `/campsites/${q.campsite.id}` : "/questions"} className="btn-ghost -ml-3 mb-2 px-3 py-1.5">
        <ArrowLeft size={16} /> {q.campsite ? q.campsite.name : "All questions"}</Link>
      <article className="card p-6">
        <div className="flex items-start gap-3">
          <h1 className="mr-auto text-xl font-extrabold">{q.title}</h1>
          <StatusBadge status={q.status} />
        </div>
        <p className="mt-1 text-xs text-ink/55">Asked by {q.author.display_name} {timeAgo(q.created_at)}{q.edited_at && " · edited"}</p>
        <p className="mt-4 whitespace-pre-line text-ink/85">{q.body}</p>
        {isAsker && open && <button className="btn-ghost btn-sm mt-4" onClick={() => run(() => api(`/questions/${q.id}/close/`, { method: "POST" }))}>Close question</button>}
      </article>
      <h2 className="mb-3 mt-6 font-bold">{q.answers.length} answer{q.answers.length === 1 ? "" : "s"}</h2>
      <ul className="space-y-3">
        {q.answers.map((a) => (
          <li key={a.id} className={`card p-4 ${a.is_accepted ? "border-forest-500 ring-1 ring-forest-500" : ""}`}>
            <div className="flex items-center gap-2">
              <Avatar name={a.author.display_name} id={a.author.id} src={a.author.avatar} size="h-8 w-8 text-xs" />
              <span className="text-sm font-semibold">{a.author.display_name}</span>
              <span className="text-xs text-ink/50">{timeAgo(a.created_at)}{a.edited_at && " · edited"}</span>
              {a.is_accepted && <span className="ml-auto inline-flex items-center gap-1 text-xs font-semibold text-forest-700"><Check size={14} /> Accepted answer</span>}
            </div>
            <p className="mt-2 whitespace-pre-line text-sm text-ink/85">{a.body}</p>
            {isAsker && open && !a.is_accepted && (
              <button className="btn-outline btn-sm mt-3" onClick={() => run(() => api(`/questions/${q.id}/accept/`, { method: "POST", body: { answer_id: a.id } }))}>
                <Check size={14} /> Accept this answer</button>
            )}
          </li>
        ))}
      </ul>
      <ErrorNote error={err} className="mt-3" />
      {user && open && (
        <form onSubmit={(e) => { e.preventDefault(); run(async () => { await api(`/questions/${q.id}/answers/`, { method: "POST", body: { body: answer } }); setAnswer(""); }); }}
              className="card mt-5 space-y-3 p-5">
          <label className="label" htmlFor="answer">Your answer</label>
          <textarea id="answer" className="input" rows={4} required value={answer} onChange={(e) => setAnswer(e.target.value)} />
          <button className="btn-primary">Post answer</button>
        </form>
      )}
      {!open && <p className="mt-5 text-sm text-ink/60">This question is closed to new answers.</p>}
      {!user && <p className="mt-5 text-sm"><Link to="/login" className="link">Log in</Link> to answer.</p>}
    </div>
  );
}
