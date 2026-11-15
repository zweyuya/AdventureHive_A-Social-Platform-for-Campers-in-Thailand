import { AlertTriangle, ArrowLeft, BadgeCheck, Droplets, ExternalLink, Flag, Flame, History, Mountain, Pencil, Phone, Share2, ShowerHead, TreePine, Users } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import CampsiteImage from "../components/CampsiteImage";
import { MiniMap } from "../components/maps";
import PermitFields, { permitBody } from "../components/PermitFields";
import { Avatar, Empty, ErrorNote, Field, Modal, NotVerifiedBadge, SectionHead, Spinner, StarPicker, Stars, StatusBadge, Tabs, isUnverified } from "../components/ui";
import { api, results } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useApi } from "../lib/hooks";
import { dateRange, fmtDate, isStale, label, splitList, timeAgo } from "../lib/format";

function Facility({ icon: Icon, title, value, on }) {
  return (
    <div className="flex items-center gap-3 rounded-lg border border-slate-200 p-3">
      <Icon size={22} className={on === false ? "text-slate-300" : "text-forest-700"} />
      <span className="text-sm"><span className="block font-semibold text-navy-900">{title}</span>
        <span className="text-ink/60">{value}</span></span>
    </div>
  );
}

function PermitNotice({ c, onSuggest }) {
  const booking = c.permit_booking_url || c.authority?.booking_url;
  const phone = c.authority?.phone;
  const fees = splitList(c.fees, /\s*(?:·|;|\n)\s*/);
  const tone = c.permit_status === "required" ? "border-sunrise-400 bg-sunrise-100/60" : "border-slate-200 bg-slate-50";
  const Row = ({ k, children }) => (
    <div className="grid gap-1 sm:grid-cols-[8rem_1fr] sm:gap-3"><dt className="font-semibold text-ink/55">{k}</dt><dd>{children}</dd></div>
  );
  return (
    <div className={`flex gap-3 rounded-xl border p-4 text-sm ${tone}`}>
      <AlertTriangle size={20} className="mt-0.5 shrink-0 text-sunrise-600" />
      <div className="min-w-0 flex-1">
        <p className="font-semibold text-navy-900">
          {c.permit_status === "required" ? "This campsite requires a permit." :
           c.permit_status === "not_required" ? "No permit is needed here." : "Permit requirements haven't been verified yet."}
        </p>
        <dl className="mt-3 space-y-2 text-ink/80">
          {fees.length > 0 && <Row k="Fees"><span className="flex flex-wrap gap-1.5">{fees.map((f) => (
            <span key={f} className="rounded-md border border-sunrise-400/50 bg-white px-2 py-0.5 font-semibold text-navy-900">{f}</span>))}</span></Row>}
          {c.permit_details && <Row k="How to get it">{c.permit_details}</Row>}
          {c.authority && <Row k="Managed by">{c.authority.name}{phone && ` · ${phone}`}</Row>}
        </dl>
        {(booking || phone) && (
          <div className="mt-3 flex flex-wrap gap-2">
            {booking && <a href={booking} target="_blank" rel="noreferrer" className="btn-primary btn-sm">Book with the park office <ExternalLink size={14} /></a>}
            {phone && <a href={`tel:${phone.replace(/[^\d+]/g, "")}`} className="btn-outline btn-sm"><Phone size={14} /> Call the park</a>}
          </div>
        )}
        <div className="mt-3 space-y-1 text-xs text-ink/55">
          <p>Source: {c.permit_info_source || "unknown"}</p>
          {c.permit_info_verified_at && (
            <p className="inline-flex items-center gap-1 rounded-full bg-forest-50 px-2.5 py-0.5 font-semibold text-forest-800">
              <BadgeCheck size={13} /> Checked by a moderator · {fmtDate(c.permit_info_verified_at)}</p>
          )}
        </div>
        {isStale(c.permit_info_verified_at) && (
          <p className="mt-3 rounded-lg border border-slate-200 bg-white p-2.5 text-xs text-ink/75">
            <span className="font-semibold text-navy-900">Old information?</span> This was last checked over a year ago. Fees and rules may have changed.
            {onSuggest && <> <button type="button" onClick={onSuggest} className="link">Suggest an edit</button></>}
          </p>
        )}
      </div>
    </div>
  );
}

function SuggestEdit({ c, onClose }) {
  const [form, setForm] = useState({ permit_status: c.permit_status, permit_details: c.permit_details, rules: c.rules,
    fees: c.fees, permit_booking_url: c.permit_booking_url, authority_id: c.authority?.id ?? "",
    has_water_source: c.has_water_source, has_restrooms: c.has_restrooms, fire_pit_allowed: c.fire_pit_allowed,
    permit_info_source: c.permit_info_source, edit_summary: "" });
  const [error, setError] = useState(null);
  const [done, setDone] = useState(false);
  const submit = async (e) => {
    e.preventDefault(); setError(null);
    try { await api(`/campsites/${c.id}/revisions/`, { method: "POST", body: permitBody(form) }); setDone(true); }
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
        <PermitFields form={form} setForm={setForm} errors={error} sourceLabel="Where did you get this information?" />
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
  const [organizerRating, setOrganizerRating] = useState(0);
  const [text, setText] = useState("");
  const [error, setError] = useState(null);
  const submit = async (e) => {
    e.preventDefault();
    if (!rating) return setError("Choose a star rating.");
    try {
      await api("/reviews/", { method: "POST", body: { trip_id: Number(tripId), rating, review_text: text,
                                                       organizer_rating: organizerRating || null } });
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
          <div><span className="label">Your rating of the campsite</span><StarPicker value={rating} onChange={setRating} label="Campsite rating" /></div>
          <div>
            <span className="label">How was the organizer, {(trips.find((t) => String(t.id) === String(tripId)) || trips[0]).organizer?.display_name || "the organizer"}? (optional)</span>
            <StarPicker value={organizerRating} onChange={setOrganizerRating} label="Organizer rating" />
            <p className="mt-1 text-xs text-ink/55">Only you see this. It counts in the organizer's average, which is shown after 3 people have rated them.</p>
          </div>
          <Field label="Your review"><textarea className="input" rows={4} maxLength={5000} value={text} onChange={(e) => setText(e.target.value)}
                                                placeholder="What should other campers know?" /></Field>
          <ErrorNote error={error} />
          <button className="btn-primary w-full">Post review</button>
        </form>
      )}
    </Modal>
  );
}

const REPORT_REASONS = [
  ["fake", "Looks fake / reviewer wasn't there"], ["misleading", "Wrong or misleading information"],
  ["offensive", "Offensive or abusive"], ["spam", "Spam or advertising"], ["other", "Other"],
];

/** Report a review to the moderators (once per person). */
function ReportReview({ review, onClose }) {
  const [reason, setReason] = useState("misleading");
  const [details, setDetails] = useState("");
  const [error, setError] = useState(null);
  const [done, setDone] = useState(false);
  const submit = async (e) => {
    e.preventDefault(); setError(null);
    try { await api(`/reviews/${review.id}/report/`, { method: "POST", body: { reason, details } }); setDone(true); }
    catch (err) { setError(err.status === 429 ? "Too many reports. Try again in a minute." : err); }
  };
  return (
    <Modal title="Report this review" onClose={onClose}>
      {done ? <>
        <p className="text-sm text-ink/75">Thanks. A moderator will check this review. If it breaks the rules it will be hidden and removed from the rating.</p>
        <button className="btn-primary mt-5 w-full" onClick={onClose}>Done</button>
      </> : (
        <form onSubmit={submit} className="space-y-4">
          <Field label="What's wrong with it?">
            <select className="input" value={reason} onChange={(e) => setReason(e.target.value)}>
              {REPORT_REASONS.map(([v, t]) => <option key={v} value={v}>{t}</option>)}</select></Field>
          <Field label="Details (optional)"><textarea className="input" rows={3} maxLength={2000} value={details} onChange={(e) => setDetails(e.target.value)} /></Field>
          <ErrorNote error={error} />
          <button className="btn-primary w-full">Send report</button>
        </form>
      )}
    </Modal>
  );
}

/**
 * Badge shows how the reviewer's attendance was recorded: checked in with the trip code,
 * marked as attended by the organizer (no check-in), or by an admin on a no-show appeal.
 * It is about attendance only: organizers can't edit or remove reviews.
 */
export function ReviewItem({ r }) {
  const { user } = useAuth();
  const [reporting, setReporting] = useState(false);
  const checkedIn = r.verification === "check_in";
  const onAppeal = r.verification === "admin_appeal";
  const visited = new Date(r.trip.start_datetime).toLocaleDateString("en-GB", { month: "short", year: "numeric" });
  return (
    <article className="border-b border-slate-100 py-4 last:border-0">
      <div className="flex items-start gap-3">
        <Avatar name={r.author.display_name} id={r.author.id} src={r.author.avatar} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-semibold">{r.author.display_name}</span>
            <span title={checkedIn ? "Checked in at the campsite with the trip code. Organizers can't edit or remove reviews."
                   : onAppeal ? "The organizer marked this person as a no-show; an admin accepted their appeal and marked them as attended. Organizers can't edit or remove reviews."
                   : "The organizer marked this person as attended. They didn't check in with the trip code. Organizers can't edit or remove reviews."}
                  className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ${checkedIn ? "bg-forest-100 text-forest-800" : "bg-slate-100 text-slate-700"}`}>
              <BadgeCheck size={13} /> {checkedIn ? "Verified attendee · checked in" : onAppeal ? "Marked as attended by an admin (appeal)" : "Marked as attended by organizer"}</span>
            <span className="ml-auto text-xs text-ink/50">{fmtDate(r.created_at)}{r.edited_at && " · edited"}</span>
          </div>
          <p className="text-xs text-ink/55">Visited {visited} · {r.trip.title}</p>
          <div className="mt-1"><Stars value={r.rating} size={15} /></div>
          {r.review_text && <p className="mt-1 text-sm text-ink/85">{r.review_text}</p>}
          <div className="mt-1 flex flex-wrap items-center gap-3 text-xs">
            {r.counts_in_rating === false && <span className="text-ink/50">Earlier visit: not counted in the rating (only this person's newest review counts)</span>}
            {user && user.id !== r.author.id && (
              <button onClick={() => setReporting(true)} className="ml-auto flex items-center gap-1 text-ink/45 hover:text-red-700"><Flag size={12} /> Report</button>
            )}
          </div>
        </div>
      </div>
      {reporting && <ReportReview review={r} onClose={() => setReporting(false)} />}
    </article>
  );
}

function QAPanel({ campsiteId, verified = true }) {
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
      {!verified ? <p className="text-sm text-ink/65">Questions open once a moderator has checked this campsite.</p> : user ? (
        <form onSubmit={ask} className="card space-y-3 p-4">
          <p className="font-semibold">Ask about this campsite</p>
          <input className="input" required maxLength={200} placeholder="Your question, e.g. Is there mobile signal?" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
          <textarea className="input" required rows={2} placeholder="Add details" value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} />
          <ErrorNote error={error} />
          <button className="btn-primary">Post question</button>
        </form>
      ) : <p className="text-sm text-ink/65"><Link to="/login" className="link">Log in</Link> to ask a question.</p>}
      {loading && <Spinner />}
      {verified && !loading && results(data).length === 0 && <Empty title="No questions yet">Be the first to ask.</Empty>}
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
          {isUnverified(c) && (
            <div className="mt-3 rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950">
              <NotVerifiedBadge />
              <p className="mt-1.5">A member suggested this campsite and a moderator hasn't checked it yet, so details such as fees and permits may be wrong.
                Trips and questions open once it's verified.</p>
              {c.is_mine && <p className="mt-1 text-xs text-amber-900/80">You suggested it. You'll get a notification when a moderator decides.</p>}
            </div>
          )}
          {!["published", "pending_review"].includes(c.status) && <p className="mt-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">This campsite is <StatusBadge status={c.status} /> and only visible to you.{c.moderation_note && ` Moderator note: ${c.moderation_note}`}</p>}

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
                <PermitNotice c={c} onSuggest={user && c.status === "published" ? () => setModal("edit") : null} />
                {c.description && <p className="max-w-prose text-ink/80">{c.description}</p>}
                {c.rules && <div><h3 className="font-bold">Rules</h3>
                  <ul className="mt-1 max-w-prose list-disc space-y-0.5 pl-5 text-sm text-ink/80">{splitList(c.rules).map((r) => <li key={r}>{r}</li>)}</ul></div>}
                <div className="flex flex-wrap items-center gap-3 border-t border-slate-100 pt-4 text-sm text-ink/60">
                  <History size={16} /> Version {c.current_version} · last updated {fmtDate(c.updated_at)}
                  {user && c.status === "published" && <button onClick={() => setModal("edit")} className="btn-outline btn-sm ml-auto"><Pencil size={14} /> Suggest an edit</button>}
                </div>
              </div>
            )}
            {tab === "trips" && (openTrips.length ? (
              <ul className="space-y-3">{openTrips.map((t) => <TripRow key={t.id} t={t} />)}</ul>
            ) : <Empty title="No upcoming trips here" action={c.status === "published"
                  ? <Link to={`/trips/new?campsite=${c.id}`} className="btn-primary">Organise a trip</Link> : null}>
                  {isUnverified(c) && "Trips can be organised here once a moderator has checked this campsite."}</Empty>)}
            {tab === "reviews" && <ReviewList reviews={reviews} onWrite={() => setModal("review")} user={user} c={c} />}
            {tab === "qa" && <QAPanel campsiteId={c.id} verified={c.status === "published"} />}
            {tab === "map" && <MiniMap lat={c.latitude} lng={c.longitude} className="h-96" />}
            {tab === "history" && <HistoryPanel campsiteId={c.id} />}
          </div>
        </div>

        <aside className="space-y-6">
          <section className="card p-4">
            <SectionHead title="Upcoming trips here" action={c.status === "published" && <Link to={`/trips/new?campsite=${c.id}`} className="link text-sm">Organise one</Link>} />
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

/**
 * "4.6 from 23 verified reviews" plus one bar per star level (5 → 1).
 * Single series: one colour (sunrise-600, validated ≥ 3:1 on white), counts shown
 * as text next to each bar, hover/focus shows the share. Same reviews as the
 * average: published, newest review per person.
 */
function RatingBreakdown({ c, compact }) {
  const counts = c.rating_breakdown || {};
  const total = c.review_count || 0;
  const max = Math.max(1, ...Object.values(counts));
  if (!total) return null;
  const from = `from ${total} verified review${total === 1 ? "" : "s"}`;
  return (
    <section className={`mb-4 rounded-xl border border-slate-200 p-4 ${compact ? "space-y-3" : "flex flex-col gap-4 sm:flex-row sm:items-center sm:gap-8"}`} aria-label="Rating breakdown">
      {compact ? ( // narrow sidebar: summary on one line, bars below
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="text-3xl font-extrabold text-navy-900">{Number(c.avg_rating).toFixed(1)}</span>
          <Stars value={c.avg_rating} size={15} />
          <span className="text-xs text-ink/60">{from}</span>
        </div>
      ) : (
        <div className="shrink-0 text-center sm:w-36">
          <p className="text-4xl font-extrabold text-navy-900">{Number(c.avg_rating).toFixed(1)}</p>
          <div className="mt-1 flex justify-center"><Stars value={c.avg_rating} size={15} /></div>
          <p className="mt-1 text-xs text-ink/60">{from}</p>
        </div>
      )}
      <ul className="flex-1 space-y-1.5">
        {[5, 4, 3, 2, 1].map((star) => {
          const n = counts[star] ?? 0;
          const pct = Math.round((n / total) * 100);
          return (
            <li key={star} tabIndex={0} className="group relative flex items-center gap-3 rounded text-sm outline-none focus-visible:ring-2 focus-visible:ring-forest-500"
                aria-label={`${star} star: ${n} review${n === 1 ? "" : "s"} (${pct}%)`}>
              <span className="w-8 shrink-0 text-ink/70">{star} ★</span>
              <span className="h-2.5 flex-1 rounded bg-slate-100">
                {n > 0 && <span className="block h-full rounded bg-sunrise-600" style={{ width: `${(n / max) * 100}%` }} />}
              </span>
              <span className="w-8 shrink-0 text-right tabular-nums text-ink/70">{n}</span>
              <span role="tooltip" className="pointer-events-none absolute -top-8 left-1/2 z-10 hidden -translate-x-1/2 whitespace-nowrap rounded-md bg-navy-900 px-2 py-1 text-xs text-white shadow group-hover:block group-focus-visible:block">
                {star} ★ · {n} review{n === 1 ? "" : "s"} · {pct}%
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function ReviewList({ reviews, onWrite, user, compact, c }) {
  const items = results(reviews.data);
  return (
    <div>
      <div className="mb-2 flex items-center justify-between gap-3">
        <h2 className="text-lg font-bold">Reviews</h2>
        {user && c?.status !== "pending_review" && <button onClick={onWrite} className="btn-primary btn-sm">Write a review</button>}
      </div>
      {c && <RatingBreakdown c={c} compact={compact} />}
      <p className="text-xs text-ink/55">Only campers who attended a trip here can review. Each person counts once in the rating (their newest review). The badge shows how their attendance was recorded; organizers can't edit or remove reviews.</p>
      {reviews.loading && <Spinner />}
      {!reviews.loading && items.length === 0 && <p className="mt-3 text-sm text-ink/60">No reviews yet.</p>}
      {(compact ? items.slice(0, 3) : items).map((r) => <ReviewItem key={r.id} r={r} />)}
    </div>
  );
}
