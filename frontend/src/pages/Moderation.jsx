import { AlertTriangle, Check, MapPin, ShieldCheck, X } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import CampsiteImage from "../components/CampsiteImage";
import { PinsMap, campIcon, meetIcon } from "../components/maps";
import { Empty, ErrorNote, Spinner, StatusBadge } from "../components/ui";
import { api, results } from "../lib/api";
import { useAuth } from "../lib/auth";
import { fmtDate, label } from "../lib/format";
import { useApi } from "../lib/hooks";

function Fact({ k, v }) {
  if (v === null || v === undefined || v === "") return null;
  return <p className="text-sm"><span className="text-ink/55">{k}: </span><span className="whitespace-pre-line text-navy-900">{v}</span></p>;
}

const yesNo = (v) => (v ? "Yes" : "No");

function PinCheck({ c }) {
  const { problem, province } = c.pin_check;
  return problem
    ? <p className="flex items-start gap-2 rounded-lg bg-red-50 p-3 text-sm text-red-800"><AlertTriangle size={16} className="mt-0.5 shrink-0" /> {problem}</p>
    : <p className="flex items-start gap-2 rounded-lg bg-forest-50 p-3 text-sm text-forest-800"><Check size={16} className="mt-0.5 shrink-0" /> The pin is in Thailand, in {province}.</p>;
}

function Nearby({ c }) {
  if (!c.nearby.length) return <p className="text-sm text-ink/60">No other campsites within 1 km.</p>;
  return (
    <div className="rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
      <p className="flex items-center gap-2 font-semibold"><AlertTriangle size={16} /> Possible duplicate: {c.nearby.length} within 1 km</p>
      <ul className="mt-1 space-y-1">
        {c.nearby.map((n) => (
          <li key={n.id} className="flex flex-wrap items-center gap-2">
            {n.status === "published" ? <Link to={`/campsites/${n.id}`} className="link">{n.name}</Link> : <span className="font-semibold">{n.name}</span>}
            <span className="text-xs">{n.distance_km} km away</span>
            {n.status !== "published" && <StatusBadge status={n.status} />}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Decision({ c, onDone }) {
  const [rejecting, setRejecting] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const send = async (action, body, flash) => {
    setBusy(true); setError(null);
    try { await api(`/campsites/${c.id}/${action}/`, { method: "POST", body }); onDone(flash); }
    catch (err) { setError(err); setBusy(false); }
  };
  const approve = () => send("approve", undefined, `Approved "${c.name}". It is now public.`);
  const reject = (e) => {
    e.preventDefault();
    send("reject", { note }, `Rejected "${c.name}". The submitter can see your reason.`);
  };

  if (rejecting) return (
    <form onSubmit={reject} className="space-y-2">
      <label className="block text-sm font-semibold" htmlFor={`note-${c.id}`}>Reason (shown to the submitter)</label>
      <textarea id={`note-${c.id}`} className="input text-sm" rows={3} required maxLength={2000} autoFocus
                placeholder="e.g. This is the same place as Lam Ta Khong Campground." value={note} onChange={(e) => setNote(e.target.value)} />
      <ErrorNote error={error} />
      <div className="flex gap-2">
        <button className="btn-danger" disabled={busy || !note.trim()}><X size={16} /> Reject</button>
        <button type="button" className="btn-ghost" onClick={() => setRejecting(false)}>Back</button>
      </div>
    </form>
  );
  return (
    <div className="space-y-2">
      {confirming && <p className="text-sm font-semibold text-amber-900">Are you sure this is not a duplicate?</p>}
      <ErrorNote error={error} />
      <div className="flex flex-wrap gap-2">
        <button className="btn-primary" disabled={busy || !!c.pin_check.problem}
                onClick={() => (c.nearby.length && !confirming ? setConfirming(true) : approve())}>
          <Check size={16} /> {confirming ? "Yes, approve" : "Approve"}
        </button>
        <button className="btn-danger" disabled={busy} onClick={() => setRejecting(true)}><X size={16} /> Reject</button>
      </div>
      {c.pin_check.problem && <p className="text-xs text-ink/60">Fix the pin first: reject this with a reason so the submitter can move it.</p>}
    </div>
  );
}

function Submission({ c, onDone }) {
  const pins = [
    { position: [c.latitude, c.longitude], icon: meetIcon, title: `This submission: ${c.name}` },
    ...c.nearby.map((n) => ({ position: [n.latitude, n.longitude], icon: campIcon, title: `${n.name} (${n.distance_km} km)` })),
  ];
  return (
    <article className="card overflow-hidden">
      <div className="grid gap-5 p-5 lg:grid-cols-2">
        <div className="space-y-3">
          <div>
            <h2 className="text-lg font-bold">{c.name}</h2>
            <p className="text-sm text-ink/60">
              <MapPin size={14} className="mr-1 inline" />{c.province} · {label(c.category)} · from {c.submitted_by?.display_name || "unknown"} · sent {fmtDate(c.updated_at)}
            </p>
          </div>
          {c.moderation_note && <p className="rounded-lg bg-slate-100 p-3 text-sm"><span className="font-semibold">Rejected before:</span> {c.moderation_note}</p>}
          {c.cover_image && <CampsiteImage src={c.cover_image} seed={c.id} className="h-36 w-full rounded-lg" />}
          {c.description && <p className="text-sm text-ink/85">{c.description}</p>}
          <div className="grid gap-1 sm:grid-cols-2">
            <Fact k="Water" v={yesNo(c.has_water_source)} />
            <Fact k="Restrooms" v={yesNo(c.has_restrooms)} />
            <Fact k="Fire pit" v={yesNo(c.fire_pit_allowed)} />
            <Fact k="Capacity" v={c.site_capacity} />
            <Fact k="Terrain" v={c.terrain_type} />
            <Fact k="Elevation (m)" v={c.elevation_m} />
            <Fact k="Permit" v={label(c.permit_status)} />
            <Fact k="Authority" v={c.authority?.name} />
          </div>
          <Fact k="Fees" v={c.fees} />
          <Fact k="Permit details" v={c.permit_details} />
          <Fact k="Rules" v={c.rules} />
          <Fact k="Booking link" v={c.permit_booking_url} />
          <Fact k="Permit information from" v={c.permit_info_source} />
        </div>
        <div className="space-y-3">
          <PinsMap pins={pins} className="h-56" maxZoom={14} />
          <p className="text-xs text-ink/55">Orange: this submission. Green: campsites within 1 km.</p>
          <PinCheck c={c} />
          <Nearby c={c} />
          <Decision c={c} onDone={onDone} />
        </div>
      </div>
    </article>
  );
}

/** Campsite submissions waiting for a decision. Moderators and admins only; the API checks too. */
export default function Moderation() {
  const { user } = useAuth();
  const { data, loading, error, reload } = useApi(user?.can_moderate ? "/campsites/moderation/" : null);
  const [flash, setFlash] = useState(null);
  if (!user?.can_moderate) {
    return <div className="mx-auto max-w-md px-4 py-16"><Empty title="Moderators only">This page is for campsite moderators.</Empty></div>;
  }
  const items = results(data);
  const onDone = (message) => { setFlash(message); reload(); window.scrollTo(0, 0); };
  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <h1 className="flex items-center gap-2 text-2xl font-extrabold"><ShieldCheck size={24} className="text-forest-700" /> Campsite moderation</h1>
      <p className="mb-4 text-ink/60">{data ? `${data.count} waiting for a decision, oldest first.` : "Campsites waiting for a decision."}</p>
      {flash && <p className="mb-4 rounded-lg bg-forest-50 p-3 text-sm text-forest-800">{flash}</p>}
      <ErrorNote error={error} className="mb-4" />
      {loading && !data && <Spinner />}
      {data && items.length === 0 && <Empty title="Nothing to review">New campsite submissions will appear here.</Empty>}
      <div className="space-y-5">
        {items.map((c) => <Submission key={c.id} c={c} onDone={onDone} />)}
      </div>
    </div>
  );
}
