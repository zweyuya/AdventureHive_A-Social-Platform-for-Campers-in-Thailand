import { AlertTriangle, ArrowLeft, BadgeCheck, Droplets, Flame, History, Mountain, Pencil, Share2, ShowerHead, TreePine, Users } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import CampsiteImage from "../components/CampsiteImage";
import { MiniMap } from "../components/maps";
import { Avatar, Empty, ErrorNote, Field, Modal, SectionHead, Spinner, StarPicker, Stars, StatusBadge, Tabs } from "../components/ui";
import { api, results } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useApi } from "../lib/hooks";
import { dateRange, fmtDate, label, timeAgo } from "../lib/format";

function Facility({ icon: Icon, title, value, on }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-slate-200 p-3">
      <Icon size={22} className={on === false ? "text-slate-300" : "text-forest-700"} />
      <span className="text-sm"><span className="block font-semibold text-navy-900">{title}</span>
        <span className="text-ink/60">{value}</span></span>
    </div>
  );
}

function PermitNotice({ c }) {
  const booking = c.permit_booking_url || c.authority?.booking_url;
  const tone = c.permit_status === "required" ? "border-sunrise-400 bg-sunrise-100/60" : "border-slate-200 bg-slate-50";
  return (
    <div className={`flex gap-3 rounded-xl border p-4 text-sm ${tone}`}>
      <AlertTriangle size={20} className="mt-0.5 shrink-0 text-sunrise-600" />
      <div>
        <p className="font-semibold text-navy-900">
          {c.permit_status === "required" ? "This campsite requires a permit." :
           c.permit_status === "not_required" ? "No permit is needed here." : "Permit requirements haven't been verified yet."}
        </p>
        {c.permit_details && <p className="mt-1 text-ink/75">{c.permit_details}</p>}
        {c.authority && <p className="mt-1 text-ink/75">Managed by {c.authority.name}{c.authority.phone && ` · ${c.authority.phone}`}</p>}
        {booking && <a href={booking} target="_blank" rel="noreferrer" className="link mt-1 inline-block">Book with the park office</a>}
        <p className="mt-1 text-xs text-ink/50">Source: {c.permit_info_source || "unknown"}{c.permit_info_verified_at && ` · checked ${fmtDate(c.permit_info_verified_at)}`}</p>
      </div>
    </div>
  );
}

function SuggestEdit({ c, onClose }) {
  const [form, setForm] = useState({ permit_status: c.permit_status, permit_details: c.permit_details, rules: c.rules,
    has_water_source: c.has_water_source, has_restrooms: c.has_restrooms, fire_pit_allowed: c.fire_pit_allowed,
    permit_info_source: "", edit_summary: "" });
  const [error, setError] = useState(null);
  const [done, setDone] = useState(false);
  const submit = async (e) => {
    e.preventDefault(); setError(null);
    try { await api(`/campsites/${c.id}/revisions/`, { method: "POST", body: form }); setDone(true); }
    catch (err) { setError(err); }
  };
  if (done) return (
    <Modal title="Thanks for the update" onClose={onClose}>
      <p className="text-sm text-ink/75">A moderator will review your suggestion. Once approved it becomes version {c.current_version + 1} of this campsite, and you'll get a notification.</p>
      <button className="btn-primary mt-5 w-full" onClick={onClose}>Done</button>
    </Modal>
  );
  return (
    <Modal title="Suggest an edit" onClose={onClose} wide>
      <form onSubmit={submit} className="space-y-4">
        <p className="text-sm text-ink/65">Changes are checked by a moderator before they appear. Every approved change is kept in the campsite's history.</p>
        <div className="flex flex-wrap gap-4">
          {[["has_water_source", "Water source"], ["has_restrooms", "Restrooms"], ["fire_pit_allowed", "Fire pit allowed"]].map(([k, t]) => (
            <label key={k} className="flex items-center gap-2 text-sm"><input type="checkbox" className="h-4 w-4 accent-forest-700"
              checked={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.checked })} /> {t}</label>
          ))}
        </div>
        <Field label="Permit">
          <select className="input" value={form.permit_status} onChange={(e) => setForm({ ...form, permit_status: e.target.value })}>
            <option value="required">Required</option><option value="not_required">Not required</option><option value="unknown">Unknown</option>
          </select>
        </Field>
        <Field label="Permit details"><textarea className="input" rows={2} value={form.permit_details} onChange={(e) => setForm({ ...form, permit_details: e.target.value })} /></Field>
        <Field label="Rules"><textarea className="input" rows={2} value={form.rules} onChange={(e) => setForm({ ...form, rules: e.target.value })} /></Field>
        <Field label="Where did you get this information?"><input className="input" placeholder="e.g. Sign at the park gate, DNP website" value={form.permit_info_source} onChange={(e) => setForm({ ...form, permit_info_source: e.target.value })} /></Field>
        <Field label="Summary of your change" required><input className="input" required maxLength={300} placeholder="e.g. Added permit fee from the gate sign" value={form.edit_summary} onChange={(e) => setForm({ ...form, edit_summary: e.target.value })} /></Field>
        <ErrorNote error={error} />
        <button className="btn-primary w-full">Send for review</button>
      </form>
    </Modal>
  );
}

export function WriteReview({ campsiteId, trips, onClose, onDone }) {
  const [tripId, setTripId] = useState(trips[0]?.id || "");
  const [rating, setRating] = useState(0);
  const [text, setText] = useState("");
  const [error, setError] = useState(null);
  const submit = async (e) => {
    e.preventDefault();
    if (!rating) return setError("Choose a star rating.");
    try {
      await api("/reviews/", { method: "POST", body: { trip_id: Number(tripId), rating, review_text: text } });
      onDone();
    } catch (err) { setError(err); }
  };
  return (
    <Modal title="Write a review" onClose={onClose}>
      {trips.length === 0 ? (
        <div className="text-sm text-ink/75">
          <p>Reviews on AdventureHive come only from people who were there. You can review this campsite after you join a trip here and the organizer marks you as attended.</p>
          <Link to={`/trips?location=${campsiteId}`} className="btn-primary mt-5 w-full" onClick={onClose}>See trips to this campsite</Link>
        </div>
      ) : (
        <form onSubmit={submit} className="space-y-4">
          {trips.length > 1 && (
            <Field label="Trip">
              <select className="input" value={tripId} onChange={(e) => setTripId(e.target.value)}>
                {trips.map((t) => <option key={t.id} value={t.id}>{t.title} ({dateRange(t.start_datetime, t.end_datetime)})</option>)}
              </select>
            </Field>
          )}
          {trips.length === 1 && <p className="text-sm text-ink/70">From your trip: <span className="font-semibold">{trips[0].title}</span></p>}
          <div><span className="label">Your rating</span><StarPicker value={rating} onChange={setRating} /></div>
          <Field label="Your review"><textarea className="input" rows={4} maxLength={5000} value={text} onChange={(e) => setText(e.target.value)}
                                                placeholder="What should other campers know?" /></Field>
          <ErrorNote error={error} />
          <button className="btn-primary w-full">Post review</button>
        </form>
      )}
    </Modal>
  );
}

export function ReviewItem({ r }) {
  return (
    <article className="border-b border-slate-100 py-4 last:border-0">
      <div className="flex items-start gap-3">
        <Avatar name={r.author.display_name} id={r.author.id} src={r.author.avatar} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold">{r.author.display_name}</span>
            <span className="inline-flex items-center gap-1 rounded-full bg-forest-100 px-2 py-0.5 text-xs font-semibold text-forest-800">
              <BadgeCheck size={13} /> Verified attendee</span>
            <span className="ml-auto text-xs text-ink/50">{fmtDate(r.created_at)}{r.edited_at && " · edited"}</span>
          </div>
          <p className="text-xs text-ink/55">{r.trip.title} · {fmtDate(r.trip.start_datetime)}</p>
          <div className="mt-1"><Stars value={r.rating} size={15} /></div>
          {r.review_text && <p className="mt-1 text-sm text-ink/85">{r.review_text}</p>}
        </div>
      </div>
    </article>
  );
}

function QAPanel({ campsiteId }) {
  const { user } = useAuth();
  const { data, loading, reload } = useApi(`/questions/?location=${campsiteId}`);
  const [form, setForm] = useState({ title: "", body: "" });
  const [error, setError] = useState(null);
  const ask = async (e) => {
    e.preventDefault(); setError(null);
    try { await api("/questions/", { method: "POST", body: { ...form, location_id: campsiteId } }); setForm({ title: "", body: "" }); reload(); }
    catch (err) { setError(err); }
  };
  return (
    <div className="space-y-5">
      {user ? (
        <form onSubmit={ask} className="card space-y-3 p-4">
          <p className="font-semibold">Ask about this campsite</p>
          <input className="input" required maxLength={200} placeholder="Your question, e.g. Is there mobile signal?" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
          <textarea className="input" required rows={2} placeholder="Add details" value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} />
          <ErrorNote error={error} />
          <button className="btn-primary">Post question</button>
        </form>
      ) : <p className="text-sm text-ink/65"><Link to="/login" className="link">Log in</Link> to ask a question.</p>}
      {loading && <Spinner />}
      {!loading && results(data).length === 0 && <Empty title="No questions yet">Be the first to ask.</Empty>}
      <ul className="divide-y divide-slate-100">
        {results(data).map((q) => (
          <li key={q.id} className="py-3">
            <Link to={`/questions/${q.id}`} className="font-semibold text-navy-900 hover:text-forest-800">{q.title}</Link>
            <p className="mt-1 flex items-center gap-2 text-xs text-ink/55">
              <StatusBadge status={q.status} /> {q.answer_count} answer{q.answer_count === 1 ? "" : "s"} · asked by {q.author.display_name} {timeAgo(q.created_at)}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}

function HistoryPanel({ campsiteId }) {
  const { data, loading } = useApi(`/campsites/${campsiteId}/history/`);
  if (loading) return <Spinner />;
  return (
    <ol className="space-y-3">
      {(data || []).map((v) => (
        <li key={v.id} className="flex gap-3 rounded-lg border border-slate-200 p-3 text-sm">
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-forest-100 text-xs font-bold text-forest-800">v{v.version_no}</span>
          <span><span className="font-semibold text-navy-900">{v.edit_summary || "Updated"}</span>
            <span className="block text-ink/60">by {v.edited_by} · {fmtDate(v.created_at)}</span></span>
        </li>
      ))}
    </ol>
  );
}

export default function CampsiteDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const { data: c, loading, error } = useApi(`/campsites/${id}/`);
  const trips = useApi(`/trips/?location=${id}`);
  const reviews = useApi(`/campsites/${id}/reviews/`);
  const mine = useApi(user ? "/trips/mine/" : null);
  const [tab, setTab] = useState("overview");
  const [modal, setModal] = useState(null);
  const [copied, setCopied] = useState(false);

  if (loading) return <Spinner />;
  if (error) return <div className="mx-auto max-w-3xl p-6"><ErrorNote error={error.status === 404 ? "This campsite doesn't exist or isn't published yet." : error} /></div>;

  const reviewable = (mine.data || []).filter((t) => t.location.id === c.id && t.status === "completed" && t.my_status === "attended");
  const openTrips = results(trips.data);
  const share = async () => { await navigator.clipboard?.writeText(window.location.href); setCopied(true); setTimeout(() => setCopied(false), 2000); };

  return (
    <div className="mx-auto max-w-7xl px-4 py-6">
      <Link to="/campsites" className="btn-ghost -ml-3 mb-3 px-3 py-1.5"><ArrowLeft size={16} /> All campsites</Link>
      <div className="grid gap-6 lg:grid-cols-[1fr_380px]">
        <div className="min-w-0">
          <section className="relative overflow-hidden rounded-2xl">
            <CampsiteImage src={c.cover_image} seed={c.id} className="h-64 w-full sm:h-72" alt={c.cover_image ? `Photo of ${c.name}` : `Illustration of ${c.name}`} />
            <div className="absolute inset-0 flex flex-col justify-end bg-gradient-to-t from-navy-900/80 via-navy-900/20 to-transparent p-6">
              <h1 className="text-2xl font-extrabold !text-white sm:text-3xl">{c.name}</h1>
              <div className="mt-2 flex flex-wrap items-center gap-3 text-sm text-white/90">
                <span className="rounded-full bg-forest-600 px-2.5 py-0.5 text-xs font-semibold">{label(c.category)}</span>
                <span>{c.province}</span>
                {c.avg_rating ? <span className="flex items-center gap-1"><Stars value={c.avg_rating} size={15} /> {Number(c.avg_rating).toFixed(1)} ({c.review_count} reviews)</span>
                  : <span>No reviews yet</span>}
              </div>
            </div>
            <button onClick={share} className="absolute right-3 top-3 rounded-lg bg-white/90 p-2 text-ink hover:bg-white" aria-label="Copy link">
              <Share2 size={18} />
            </button>
            {copied && <span className="absolute right-14 top-4 rounded bg-white px-2 py-1 text-xs">Link copied</span>}
          </section>
          {c.cover_image_credit && <p className="mt-1 text-right text-xs text-ink/50">{c.cover_image_credit}</p>}
          {c.status !== "published" && <p className="mt-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">This campsite is <StatusBadge status={c.status} /> and only visible to you.{c.moderation_note && ` Moderator note: ${c.moderation_note}`}</p>}

          <div className="mt-4"><Tabs active={tab} onChange={setTab} tabs={[["overview", "Overview"], ["trips", `Trips (${openTrips.length})`],
            ["reviews", `Reviews (${c.review_count})`], ["qa", "Q&A"], ["map", "Map"], ["history", "History"]]} /></div>

          <div className="py-5">
            {tab === "overview" && (
              <div className="space-y-5">
                <div>
                  <h2 className="mb-3 text-lg font-bold">Facilities and information</h2>
                  <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                    <Facility icon={Droplets} title="Water source" value={c.has_water_source ? "Available" : "Not available"} on={c.has_water_source} />
                    <Facility icon={ShowerHead} title="Restrooms" value={c.has_restrooms ? "Available" : "Not available"} on={c.has_restrooms} />
                    <Facility icon={Flame} title="Fire pit" value={c.fire_pit_allowed ? "Allowed" : "Not allowed"} on={c.fire_pit_allowed} />
                    <Facility icon={Users} title="Site capacity" value={c.site_capacity ? `${c.site_capacity} people` : "Unknown"} />
                    <Facility icon={Mountain} title="Elevation" value={c.elevation_m ? `${c.elevation_m} m` : "Unknown"} />
                    <Facility icon={TreePine} title="Terrain" value={c.terrain_type || "Unknown"} />
                  </div>
                </div>
                <PermitNotice c={c} />
                {c.description && <p className="max-w-prose text-ink/80">{c.description}</p>}
                {c.rules && <div><h3 className="font-bold">Rules</h3><p className="mt-1 max-w-prose text-sm text-ink/80">{c.rules}</p></div>}
                <div className="flex flex-wrap items-center gap-3 border-t border-slate-100 pt-4 text-sm text-ink/60">
                  <History size={16} /> Version {c.current_version} · last updated {fmtDate(c.updated_at)}
                  {user && c.status === "published" && <button onClick={() => setModal("edit")} className="btn-outline btn-sm ml-auto"><Pencil size={14} /> Suggest an edit</button>}
                </div>
              </div>
            )}
            {tab === "trips" && (openTrips.length ? (
              <ul className="space-y-3">{openTrips.map((t) => <TripRow key={t.id} t={t} />)}</ul>
            ) : <Empty title="No upcoming trips here" action={<Link to={`/trips/new?campsite=${c.id}`} className="btn-primary">Organise a trip</Link>} />)}
            {tab === "reviews" && <ReviewList reviews={reviews} onWrite={() => setModal("review")} user={user} />}
            {tab === "qa" && <QAPanel campsiteId={c.id} />}
            {tab === "map" && <MiniMap lat={c.latitude} lng={c.longitude} className="h-96" />}
            {tab === "history" && <HistoryPanel campsiteId={c.id} />}
          </div>
        </div>

        <aside className="space-y-6">
          <section className="card p-4">
            <SectionHead title="Upcoming trips here" action={<Link to={`/trips/new?campsite=${c.id}`} className="link text-sm">Organise one</Link>} />
            {openTrips.length === 0 ? <p className="text-sm text-ink/60">No trips planned yet.</p>
              : <ul className="space-y-3">{openTrips.slice(0, 3).map((t) => <TripRow key={t.id} t={t} compact />)}</ul>}
          </section>
          <section className="card p-4">
            <ReviewList reviews={reviews} onWrite={() => setModal("review")} user={user} compact c={c} />
          </section>
        </aside>
      </div>
      {modal === "edit" && <SuggestEdit c={c} onClose={() => setModal(null)} />}
      {modal === "review" && <WriteReview campsiteId={c.id} trips={reviewable} onClose={() => setModal(null)}
                                          onDone={() => { setModal(null); reviews.reload(); mine.reload(); }} />}
    </div>
  );
}

function TripRow({ t, compact }) {
  const pct = Math.round((t.confirmed_count / t.participant_capacity) * 100);
  return (
    <li className="flex items-center gap-3">
      <CampsiteImage src={t.location.cover_image} seed={t.location.id * 31 + t.id} className={`${compact ? "h-14 w-20" : "h-16 w-24"} shrink-0 rounded-lg`} />
      <div className="min-w-0 flex-1">
        <Link to={`/trips/${t.id}`} className="block truncate text-sm font-semibold text-navy-900 hover:text-forest-800">{t.title}</Link>
        <p className="text-xs text-ink/60">{dateRange(t.start_datetime, t.end_datetime)} · by {t.organizer.display_name}</p>
        <div className="mt-1 flex items-center gap-2 text-xs text-ink/60">
          <span className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-200"><span className="block h-full bg-forest-600" style={{ width: `${pct}%` }} /></span>
          {t.confirmed_count}/{t.participant_capacity}
        </div>
      </div>
      <Link to={`/trips/${t.id}`} className="btn-outline btn-sm">View</Link>
    </li>
  );
}

function ReviewList({ reviews, onWrite, user, compact, c }) {
  const items = results(reviews.data);
  return (
    <div>
      <div className="mb-2 flex items-center justify-between gap-3">
        <h2 className="text-lg font-bold">Reviews {compact && c?.avg_rating && <span className="ml-1 text-sm font-semibold text-ink/70">
          <Stars value={c.avg_rating} size={14} /> {Number(c.avg_rating).toFixed(1)}</span>}</h2>
        {user && <button onClick={onWrite} className="btn-primary btn-sm">Write a review</button>}
      </div>
      <p className="text-xs text-ink/55">Only campers the trip organizer marked as attended can review.</p>
      {reviews.loading && <Spinner />}
      {!reviews.loading && items.length === 0 && <p className="mt-3 text-sm text-ink/60">No reviews yet.</p>}
      {(compact ? items.slice(0, 3) : items).map((r) => <ReviewItem key={r.id} r={r} />)}
    </div>
  );
}
