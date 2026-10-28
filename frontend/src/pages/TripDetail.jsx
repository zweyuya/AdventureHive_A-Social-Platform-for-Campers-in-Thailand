import { ArrowLeft, Calendar, Check, Clock, Footprints, Gauge, KeyRound, LifeBuoy, Lock, MapPin, Mountain, Pencil, Route, Share2, ShieldAlert, Tent, Trash2, UserCheck, Users, X } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import CampsiteImage from "../components/CampsiteImage";
import { PinsMap, campIcon, meetIcon } from "../components/maps";
import { Avatar, ErrorNote, Modal, Spinner, StatusBadge } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useApi } from "../lib/hooks";
import { dateRange, fmtDate, fmtTime, label, timeAgo } from "../lib/format";
import { WriteReview } from "./CampsiteDetail";
import { PostComposer, PostList } from "../components/feed";

function Row({ icon: Icon, k, v }) {
  if (v === null || v === undefined || v === "") return null;
  return (
    <div className="flex gap-3 py-1.5 text-sm">
      <Icon size={16} className="mt-0.5 shrink-0 text-forest-700" />
      <span className="w-36 shrink-0 text-ink/60">{k}</span>
      <span className="text-navy-900">{v}</span>
    </div>
  );
}

function JoinCard({ trip, user, onChange }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const act = async (method) => {
    setBusy(true); setError(null);
    try { await api(`/trips/${trip.id}/rsvp/`, { method }); await onChange(); }
    catch (err) { setError(err.status === 429 ? "You're doing that too often. Wait a minute." : err); }
    finally { setBusy(false); }
  };
  const open = ["published", "full"].includes(trip.status) && new Date(trip.start_datetime) > new Date();
  const isOrganizer = user && trip.organizer.id === user.id;
  let body;
  if (isOrganizer) body = <p className="text-sm text-ink/70">You're organising this trip.</p>;
  else if (!user) body = <Link to="/login" className="btn-primary w-full">Log in to join</Link>;
  else if (trip.my_status === "confirmed") body = (
    <>
      <p className="flex items-center gap-2 font-semibold text-forest-800"><Check size={18} /> You're going</p>
      {open && <button onClick={() => act("DELETE")} disabled={busy} className="btn-danger mt-3 w-full">Leave this trip</button>}
    </>);
  else if (trip.my_status === "waitlisted") body = (
    <>
      <p className="font-semibold text-sunrise-600">You're #{trip.my_waitlist_position} on the waitlist</p>
      <p className="mt-1 text-sm text-ink/65">If someone leaves, the first person on the waitlist gets their seat automatically.</p>
      <button onClick={() => act("DELETE")} disabled={busy} className="btn-danger mt-3 w-full">Leave the waitlist</button>
    </>);
  else if (trip.my_status === "attended") body = <p className="font-semibold text-forest-800">You attended this trip.</p>;
  else if (!open) body = <p className="text-sm text-ink/70">This trip is {trip.status === "completed" ? "over" : trip.status}.</p>;
  else body = (
    <>
      <button onClick={() => act("POST")} disabled={busy} className="btn-primary w-full py-3">
        {busy ? "Joining…" : trip.spots_left > 0 ? "Join this trip" : "Join the waitlist"}
      </button>
      <p className="mt-2 text-xs text-ink/55">Requires {trip.min_experience_level} experience or above.</p>
    </>);
  return (
    <section className="card p-5">
      <h2 className="mb-1 font-bold">Join this trip</h2>
      <p className="mb-3 text-sm text-ink/60">{trip.spots_left > 0 ? `${trip.spots_left} spot${trip.spots_left === 1 ? "" : "s"} left` : "Full — waitlist open"}</p>
      {body}
      <ErrorNote error={error} className="mt-3" />
    </section>
  );
}

/**
 * Organizer records attendance. People who checked in with the trip code are
 * pre-marked "attended". Marking someone attended who did NOT check in needs a
 * reason (forgot, phone died…); their review then shows "Confirmed by organizer".
 */
function Attendance({ trip, participants, onDone }) {
  const confirmed = participants.filter((p) => ["confirmed", "attended", "no_show"].includes(p.status));
  const initial = (p) => (p.status === "confirmed" ? (p.checked_in_at ? "attended" : "no_show") : p.status);
  const [marks, setMarks] = useState(Object.fromEntries(confirmed.map((p) => [p.user_id, initial(p)])));
  const [reasons, setReasons] = useState(Object.fromEntries(confirmed.map((p) => [p.user_id, p.override_reason || ""])));
  const [error, setError] = useState(null);
  const [saved, setSaved] = useState(false);
  const needsReason = (p) => marks[p.user_id] === "attended" && !p.checked_in_at;
  const save = async () => {
    setError(null);
    if (confirmed.some((p) => needsReason(p) && !reasons[p.user_id].trim()))
      return setError("Give a reason for everyone marked attended who did not check in.");
    try {
      await api(`/trips/${trip.id}/attendance/`, { method: "POST", body: { records: confirmed.map((p) => ({
        user_id: p.user_id, status: marks[p.user_id], ...(needsReason(p) ? { reason: reasons[p.user_id].trim() } : {}) })) } });
      setSaved(true); onDone();
    } catch (err) { setError(err); }
  };
  if (!confirmed.length) return <p className="text-sm text-ink/60">Nobody was confirmed for this trip.</p>;
  return (
    <div>
      <p className="mb-3 text-sm text-ink/65">Mark who actually came. People who checked in with your trip code are pre-selected. Only people marked as attended can review the campsite. You have 7 days after the trip ends.</p>
      <ul className="divide-y divide-slate-100">
        {confirmed.map((p) => (
          <li key={p.user_id} className="py-2">
            <div className="flex items-center gap-3">
              <Avatar name={p.display_name} id={p.user_id} src={p.avatar} size="h-8 w-8 text-xs" />
              <span className="flex-1 text-sm font-medium">{p.display_name}
                <span className={`block text-xs font-normal ${p.checked_in_at ? "text-forest-700" : "text-ink/50"}`}>
                  {p.checked_in_at ? `✓ Checked in ${fmtTime(p.checked_in_at)}` : "Did not check in"}</span></span>
              {["attended", "no_show"].map((st) => (
                <button key={st} onClick={() => setMarks({ ...marks, [p.user_id]: st })} aria-pressed={marks[p.user_id] === st}
                        className={`btn-sm rounded-lg border ${marks[p.user_id] === st ? (st === "attended" ? "border-forest-700 bg-forest-700 text-white" : "border-slate-600 bg-slate-600 text-white") : "border-slate-300"}`}>
                  {st === "attended" ? "Attended" : "No-show"}
                </button>
              ))}
            </div>
            {needsReason(p) && (
              <input className="input mt-2 text-sm" maxLength={500} placeholder="Why mark them attended without a check-in? e.g. phone battery died"
                     value={reasons[p.user_id]} onChange={(e) => setReasons({ ...reasons, [p.user_id]: e.target.value })} />
            )}
          </li>
        ))}
      </ul>
      <ErrorNote error={error} className="mt-3" />
      <button onClick={save} className="btn-primary mt-3 w-full"><UserCheck size={16} /> {saved ? "Attendance saved" : "Save attendance"}</button>
    </div>
  );
}

/**
 * Check-in, open from 2 h before the start until 24 h after the end.
 * Organizer: shows the 6-digit code. Confirmed participant: enters it.
 */
function CheckInCard({ trip, isOrganizer, onChange }) {
  const c = trip.checkin;
  const code = useApi(isOrganizer && c?.is_open ? `/trips/${trip.id}/check-in-code/` : null);
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const canCheckIn = ["confirmed", "attended", "no_show"].includes(trip.my_status);
  if (!c?.is_open || (!isOrganizer && !canCheckIn)) return null;
  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setError(null);
    try { await api(`/trips/${trip.id}/check-in/`, { method: "POST", body: { code: value } }); await onChange(); }
    catch (err) { setError(err.status === 429 ? "Too many tries. Wait a minute and ask the organizer for the code." : err); }
    finally { setBusy(false); }
  };
  return (
    <section className="card border-sunrise-400 p-5">
      <h2 className="mb-1 flex items-center gap-2 font-bold"><KeyRound size={18} className="text-sunrise-600" /> Trip check-in</h2>
      <p className="mb-3 text-xs text-ink/60">Open until {fmtDate(c.closes_at)}, {fmtTime(c.closes_at)}</p>
      {isOrganizer ? (
        code.data ? <>
          <p className="text-center font-mono text-4xl font-extrabold tracking-[0.3em] text-navy-900">{code.data.code}</p>
          <p className="mt-3 text-sm text-ink/65">Show this code to your group at the meeting point or during the trip. Each person enters it in their app to prove they came.</p>
        </> : <Spinner />
      ) : c.my_checked_in_at ? (
        <p className="flex items-center gap-2 font-semibold text-forest-800"><Check size={18} /> You checked in at {fmtTime(c.my_checked_in_at)}</p>
      ) : (
        <form onSubmit={submit} className="space-y-2">
          <p className="text-sm text-ink/65">Enter the 6-digit code from the organizer. No signal at the campsite? You can enter it until 24 hours after the trip ends.</p>
          <input className="input text-center font-mono text-xl tracking-[0.3em]" inputMode="numeric" pattern="\d{6}" maxLength={6} required
                 placeholder="000000" value={value} onChange={(e) => setValue(e.target.value.replace(/\D/g, ""))} aria-label="Check-in code" />
          <button className="btn-primary w-full" disabled={busy || value.length !== 6}>{busy ? "Checking…" : "Check in"}</button>
          <ErrorNote error={error} />
        </form>
      )}
    </section>
  );
}

/**
 * Participant: opt in to share my (encrypted) emergency contact with the organizer.
 * The organizer can only open it from 1 day before to 1 day after the trip, and I
 * get a notification when they do.
 */
function EmergencyShareCard({ trip, onChange }) {
  const e = trip.emergency;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  if (!e || trip.status === "cancelled" || !["confirmed", "attended"].includes(trip.my_status)) return null;
  const toggle = async () => {
    setBusy(true); setError(null);
    try { await api(`/trips/${trip.id}/emergency-sharing/`, { method: e.i_share ? "DELETE" : "POST" }); await onChange(); }
    catch (err) { setError(err); }
    finally { setBusy(false); }
  };
  return (
    <section className="card p-5">
      <h2 className="mb-1 flex items-center gap-2 font-bold"><LifeBuoy size={18} className="text-red-700" /> Emergency contact</h2>
      <p className="text-sm text-ink/65">
        {e.i_share ? "You share your emergency contact with the organizer for this trip." : "Your emergency contact is private. You can let the organizer see it for this trip only."}
      </p>
      <p className="mt-1 text-xs text-ink/55">They can open it from {fmtDate(e.opens_at)} until {fmtDate(e.closes_at)}. You'll get a notification if they do.</p>
      {!e.i_have_contact && !e.i_share
        ? <Link to="/profile" className="btn-outline mt-3 w-full">Add an emergency contact first</Link>
        : <button onClick={toggle} disabled={busy} className={`${e.i_share ? "btn-outline" : "btn-primary"} mt-3 w-full`}>
            {e.i_share ? "Stop sharing" : "Share with the organizer"}</button>}
      <ErrorNote error={error} className="mt-2" />
    </section>
  );
}

/** Organizer: open the contacts participants shared. Loaded only on click (each read is logged). */
function EmergencyContacts({ trip }) {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState(null);
  const e = trip.emergency;
  if (!e || trip.status === "cancelled") return null;
  if (!e.is_open) return <p className="mt-4 text-xs text-ink/55"><LifeBuoy size={12} className="mr-1 inline" />Emergency contacts that participants share can be opened from {fmtDate(e.opens_at)} until {fmtDate(e.closes_at)}.</p>;
  const open = async () => { setError(null); try { setRows(await api(`/trips/${trip.id}/emergency-contacts/`)); } catch (err) { setError(err); } };
  return (
    <div className="mt-4">
      <button onClick={open} className="btn-outline w-full"><LifeBuoy size={15} /> Emergency contacts</button>
      <ErrorNote error={error} className="mt-2" />
      {rows && (
        <Modal title="Shared emergency contacts" onClose={() => setRows(null)}>
          <p className="mb-3 text-xs text-ink/60">Only for emergencies. Each person is notified that you opened this, and the access is logged.</p>
          {rows.length === 0 ? <p className="text-sm text-ink/65">Nobody has shared an emergency contact for this trip.</p> : (
            <ul className="divide-y divide-slate-100">
              {rows.map((r) => (
                <li key={r.user_id} className="py-2 text-sm">
                  <p className="font-semibold text-navy-900">{r.display_name}</p>
                  <p className="text-ink/75">{r.name} ({r.relationship}) · <a className="link" href={`tel:${r.phone}`}>{r.phone}</a></p>
                </li>
              ))}
            </ul>
          )}
        </Modal>
      )}
    </div>
  );
}

function OrganizerPanel({ trip, reload }) {
  const navigate = useNavigate();
  const parts = useApi(`/trips/${trip.id}/participants/`, [trip.updated_at]);
  const [error, setError] = useState(null);
  const [confirmCancel, setConfirmCancel] = useState(false);
  const run = async (fn) => { setError(null); try { await fn(); await reload(); parts.reload(); } catch (err) { setError(err); } };
  const list = parts.data || [];
  const waitlist = list.filter((p) => p.status === "waitlisted");
  const going = list.filter((p) => p.status === "confirmed" || p.status === "attended");
  return (
    <section className="card border-forest-200 p-5">
      <h2 className="mb-3 font-bold">Organizer tools</h2>
      <div className="flex flex-wrap gap-2">
        {trip.status === "draft" && <button className="btn-primary" onClick={() => run(() => api(`/trips/${trip.id}/publish/`, { method: "POST" }))}>Publish trip</button>}
        {["draft", "published", "full"].includes(trip.status) && <>
          <Link to={`/trips/${trip.id}/edit`} className="btn-outline"><Pencil size={15} /> Edit</Link>
          <button className="btn-danger" onClick={() => setConfirmCancel(true)}><Trash2 size={15} /> Cancel trip</button>
        </>}
      </div>
      <ErrorNote error={error} className="mt-3" />
      <EmergencyContacts trip={trip} />
      {trip.status === "completed" ? (
        <div className="mt-4"><h3 className="mb-2 text-sm font-bold">Record attendance</h3>
          {parts.loading ? <Spinner /> : <Attendance trip={trip} participants={list} onDone={() => { reload(); parts.reload(); }} />}</div>
      ) : (
        <div className="mt-4 text-sm">
          <h3 className="mb-2 font-bold">Going ({going.length})</h3>
          {going.length === 0 && <p className="text-ink/60">No one yet.</p>}
          <ul className="space-y-1.5">{going.map((p) => <li key={p.user_id} className="flex items-center gap-2"><Avatar name={p.display_name} id={p.user_id} src={p.avatar} size="h-7 w-7 text-[10px]" />{p.display_name} <span className="text-xs text-ink/50">({p.camping_experience_level})</span></li>)}</ul>
          {waitlist.length > 0 && <>
            <h3 className="mb-2 mt-4 font-bold">Waitlist ({waitlist.length})</h3>
            <ol className="space-y-1.5">{waitlist.map((p) => <li key={p.user_id} className="flex items-center gap-2"><span className="w-5 text-xs font-bold text-sunrise-600">#{p.waitlist_position}</span>{p.display_name}</li>)}</ol>
          </>}
        </div>
      )}
      {confirmCancel && (
        <Modal title="Cancel this trip?" onClose={() => setConfirmCancel(false)}>
          <p className="text-sm text-ink/75">Everyone who joined or is on the waitlist will be notified. This can't be undone.</p>
          <div className="mt-5 flex gap-3">
            <button className="btn-ghost flex-1" onClick={() => setConfirmCancel(false)}>Keep trip</button>
            <button className="btn-danger flex-1" onClick={() => { setConfirmCancel(false); run(() => api(`/trips/${trip.id}/`, { method: "DELETE" })).then(() => navigate(`/trips/${trip.id}`)); }}>Cancel trip</button>
          </div>
        </Modal>
      )}
    </section>
  );
}

function Equipment({ trip, isOrganizer, reload }) {
  const [form, setForm] = useState({ item_name: "", provided_by: "participant", notes: "", required: true });
  const [error, setError] = useState(null);
  const editable = isOrganizer && !["cancelled", "completed"].includes(trip.status);
  const add = async (e) => {
    e.preventDefault(); setError(null);
    try { await api(`/trips/${trip.id}/equipment/`, { method: "POST", body: form }); setForm({ ...form, item_name: "", notes: "" }); reload(); }
    catch (err) { setError(err); }
  };
  const remove = async (id) => { await api(`/trips/${trip.id}/equipment/${id}/`, { method: "DELETE" }); reload(); };
  return (
    <section className="card p-5">
      <h2 className="mb-3 font-bold">Equipment</h2>
      {trip.equipment_items.length === 0 && <p className="text-sm text-ink/60">No equipment list yet.</p>}
      <ul className="space-y-3">
        {trip.equipment_items.map((i) => (
          <li key={i.id} className="flex items-start gap-3 text-sm">
            <span className={`mt-0.5 flex h-5 w-5 items-center justify-center rounded ${i.required ? "bg-forest-700 text-white" : "border border-slate-300"}`}>{i.required && <Check size={14} />}</span>
            <span className="flex-1"><span className="font-medium text-navy-900">{i.item_name}</span>
              <span className="block text-ink/60">{i.provided_by === "organizer" ? "Provided by the organizer" : "Bring your own"}{i.notes && ` · ${i.notes}`}</span></span>
            {editable && <button onClick={() => remove(i.id)} className="text-ink/40 hover:text-red-600" aria-label={`Remove ${i.item_name}`}><X size={16} /></button>}
          </li>
        ))}
      </ul>
      {editable && (
        <form onSubmit={add} className="mt-4 space-y-2 border-t border-slate-100 pt-4">
          <input className="input" required placeholder="Add an item, e.g. Headlamp" value={form.item_name} onChange={(e) => setForm({ ...form, item_name: e.target.value })} />
          <div className="flex gap-2">
            <select className="input" value={form.provided_by} onChange={(e) => setForm({ ...form, provided_by: e.target.value })}>
              <option value="participant">Bring your own</option><option value="organizer">I'll provide it</option>
            </select>
            <button className="btn-outline">Add</button>
          </div>
          <ErrorNote error={error} />
        </form>
      )}
    </section>
  );
}

export default function TripDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const { data: trip, loading, error, reload } = useApi(`/trips/${id}/`);
  const [review, setReview] = useState(false);
  const [reviewed, setReviewed] = useState(false);
  const [copied, setCopied] = useState(false);
  const [feedKey, setFeedKey] = useState(0);
  if (loading && !trip) return <Spinner />;
  if (error) return <div className="mx-auto max-w-3xl p-6"><ErrorNote error={error.status === 404 ? "This trip doesn't exist or isn't visible to you." : error} /></div>;

  const isOrganizer = user && trip.organizer.id === user.id;
  const pct = Math.round((trip.confirmed_count / trip.participant_capacity) * 100);
  const share = async () => { await navigator.clipboard?.writeText(window.location.href); setCopied(true); setTimeout(() => setCopied(false), 2000); };

  return (
    <div className="mx-auto max-w-7xl px-4 py-6">
      <Link to="/trips" className="btn-ghost -ml-3 mb-2 px-3 py-1.5"><ArrowLeft size={16} /> Back to trips</Link>
      <div className="mb-5 flex flex-wrap items-start gap-3">
        <div className="mr-auto">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-2xl font-extrabold sm:text-3xl">{trip.title}</h1>
            <StatusBadge status={trip.status} className="text-sm" />
          </div>
          <p className="mt-2 flex items-center gap-2 text-sm text-ink/65">
            <Avatar name={trip.organizer.display_name} id={trip.organizer.id} src={trip.organizer.avatar} size="h-7 w-7 text-[10px]" />
            Organised by <span className="font-semibold text-navy-900">{trip.organizer.display_name}</span> · posted {timeAgo(trip.created_at)}
          </p>
        </div>
        <button onClick={share} className="btn-outline"><Share2 size={16} /> {copied ? "Link copied" : "Share"}</button>
      </div>

      {trip.can_review && !reviewed && (
        <div className="mb-5 flex flex-wrap items-center gap-3 rounded-xl border border-forest-200 bg-forest-50 p-4">
          <p className="mr-auto text-sm"><span className="font-semibold text-forest-800">Thanks for coming!</span> You can now review {trip.location.name}.</p>
          <button className="btn-primary" onClick={() => setReview(true)}>Write a review</button>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
        <div className="min-w-0 space-y-6">
          <div className="grid gap-5 md:grid-cols-2">
            <CampsiteImage src={trip.location.cover_image} seed={trip.location.id * 31 + trip.id} className="h-64 w-full rounded-xl md:h-full" alt={trip.location.name} />
            <section className="card p-5">
              <h2 className="mb-2 font-bold">Trip details</h2>
              <Row icon={Calendar} k="Dates" v={`${dateRange(trip.start_datetime, trip.end_datetime)}, ${fmtTime(trip.start_datetime)}`} />
              <Row icon={Tent} k="Campsite" v={<Link className="link" to={`/campsites/${trip.location.id}`}>{trip.location.name}</Link>} />
              <Row icon={MapPin} k="Province" v={trip.location.province} />
              <Row icon={Mountain} k="Difficulty" v={label(trip.difficulty)} />
              <Row icon={Route} k="Distance" v={trip.distance_km && `${Number(trip.distance_km)} km`} />
              <Row icon={Clock} k="Estimated duration" v={trip.estimated_duration_hours && `${Number(trip.estimated_duration_hours)} hours`} />
              <Row icon={Gauge} k="Minimum experience" v={label(trip.min_experience_level)} />
              <Row icon={Footprints} k="Meeting point" v={trip.meeting_point_hidden ? <span className="flex items-center gap-1 text-ink/60"><Lock size={13} /> Shown to confirmed participants</span> : trip.meeting_point_name} />
              <Row icon={ShieldAlert} k="Safety notes" v={trip.safety_notes} />
            </section>
          </div>
          {trip.description && <section><h2 className="mb-2 text-lg font-bold">About this trip</h2><p className="max-w-prose whitespace-pre-line text-ink/80">{trip.description}</p></section>}
          <TripMap trip={trip} />
          {(isOrganizer || ["confirmed", "attended"].includes(trip.my_status)) && (
            <section className="space-y-4">
              <div><h2 className="text-lg font-bold">Trip posts</h2>
                <p className="text-sm text-ink/60">Only the organizer and people going can see these — share plans, carpools and photos after the trip.</p></div>
              {trip.status !== "cancelled" && <PostComposer tripId={trip.id} placeholder="Ask about gear, carpools, or share photos…" onPosted={() => setFeedKey((k) => k + 1)} />}
              <PostList query={`?trip=${trip.id}`} refreshKey={feedKey} showPlace={false}
                        empty={<p className="text-sm text-ink/55">No posts yet.</p>} />
            </section>
          )}
        </div>

        <aside className="space-y-5">
          <section className="card p-5">
            <div className="flex items-baseline justify-between"><h2 className="font-bold">Capacity</h2>
              <span className="text-lg font-bold text-navy-900">{trip.confirmed_count} / {trip.participant_capacity}</span></div>
            <div className="mt-2 h-2.5 overflow-hidden rounded-full bg-slate-200"><div className="h-full rounded-full bg-forest-600" style={{ width: `${pct}%` }} /></div>
            <p className="mt-2 flex items-center gap-2 text-sm text-ink/65"><Users size={15} /> {trip.confirmed_count} confirmed · {trip.waitlist_count} waitlisted</p>
          </section>
          <JoinCard trip={trip} user={user} onChange={reload} />
          <CheckInCard trip={trip} isOrganizer={isOrganizer} onChange={reload} />
          <EmergencyShareCard trip={trip} onChange={reload} />
          {isOrganizer && <OrganizerPanel trip={trip} reload={reload} />}
          <Equipment trip={trip} isOrganizer={isOrganizer} reload={reload} />
          <p className="text-xs text-ink/50">Created {fmtDate(trip.created_at)}</p>
        </aside>
      </div>
      {review && <WriteReview campsiteId={trip.location.id} trips={[trip]} onClose={() => setReview(false)}
                              onDone={() => { setReview(false); setReviewed(true); reload(); }} />}
    </div>
  );
}

/**
 * Campsite + meeting point on one map. The campsite is public. The meeting point
 * is only drawn when the API sent it: for anyone other than the organizer and
 * confirmed/attended participants the server returns it as null
 * (meeting_point_hidden), so it never reaches this browser.
 */
function TripMap({ trip }) {
  const showMeeting = !trip.meeting_point_hidden && trip.meeting_latitude != null && trip.meeting_longitude != null;
  const pins = [
    { position: [trip.location.latitude, trip.location.longitude], icon: campIcon,
      title: `Campsite: ${trip.location.name}`, link: { to: `/campsites/${trip.location.id}`, text: "View campsite" } },
    ...(showMeeting ? [{ position: [trip.meeting_latitude, trip.meeting_longitude], icon: meetIcon,
      title: `Meeting point: ${trip.meeting_point_name || "Meeting point"}` }] : []),
  ];
  return (
    <section>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
        <h2 className="text-lg font-bold">{showMeeting ? "Meeting point and campsite" : "Campsite location"}</h2>
        <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-ink/65">
          <span className="flex items-center gap-1"><MapPin size={14} className="text-forest-700" /> Campsite</span>
          {showMeeting && <span className="flex items-center gap-1"><MapPin size={14} className="text-sunrise-500" /> Meeting point</span>}
          {trip.meeting_point_hidden && <span className="flex items-center gap-1"><Lock size={13} /> Meeting point shown to confirmed participants</span>}
        </p>
      </div>
      <PinsMap pins={pins} className="h-64" />
      <p className="mt-1 text-xs text-ink/55">Tap a pin to see its name.</p>
    </section>
  );
}
