import { ArrowLeft, Plus, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { PinPicker } from "../components/maps";
import { ErrorNote, Field, Spinner } from "../components/ui";
import { api, ApiError, results } from "../lib/api";
import { useApi } from "../lib/hooks";
import { DIFFICULTIES, LEVELS, label } from "../lib/format";

const pad = (n) => String(n).padStart(2, "0");
const toLocalInput = (d) => { const x = new Date(d); return `${x.getFullYear()}-${pad(x.getMonth() + 1)}-${pad(x.getDate())}T${pad(x.getHours())}:${pad(x.getMinutes())}`; };
function defaultDates() {
  const s = new Date(); s.setDate(s.getDate() + 14); s.setHours(8, 0, 0, 0);
  const e = new Date(s); e.setDate(e.getDate() + 2); e.setHours(17, 0, 0, 0);
  return [toLocalInput(s), toLocalInput(e)];
}

function Card({ title, children }) {
  return <section className="card p-5"><h2 className="mb-4 font-bold">{title}</h2><div className="space-y-4">{children}</div></section>;
}

export default function TripForm() {
  const { id } = useParams();
  const editing = !!id;
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const campsites = useApi("/campsites/?page_size=100");
  const myGroups = useApi("/groups/mine/");
  const existing = useApi(editing ? `/trips/${id}/` : null);
  const [start, end] = defaultDates();
  const [form, setForm] = useState({
    title: "", description: "", location_id: params.get("campsite") || "", group_id: "",
    start_datetime: start, end_datetime: end, meeting_point_name: "", meeting: null,
    difficulty: "moderate", distance_km: "", estimated_duration_hours: "", min_experience_level: "beginner",
    participant_capacity: 8, safety_notes: "",
  });
  const [equipment, setEquipment] = useState([{ item_name: "", required: true, provided_by: "participant", notes: "" }]);
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const t = existing.data;
    if (!t) return;
    setForm({
      title: t.title, description: t.description, location_id: String(t.location.id), group_id: t.group ? String(t.group) : "",
      start_datetime: toLocalInput(t.start_datetime), end_datetime: toLocalInput(t.end_datetime),
      meeting_point_name: t.meeting_point_name || "", meeting: t.meeting_latitude ? [t.meeting_latitude, t.meeting_longitude] : null,
      difficulty: t.difficulty, distance_km: t.distance_km ?? "", estimated_duration_hours: t.estimated_duration_hours ?? "",
      min_experience_level: t.min_experience_level, participant_capacity: t.participant_capacity, safety_notes: t.safety_notes,
    });
  }, [existing.data]);

  const site = useMemo(() => results(campsites.data).find((c) => String(c.id) === String(form.location_id)), [campsites.data, form.location_id]);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const save = async (publish) => {
    setBusy(true); setErrors({});
    const body = {
      title: form.title, description: form.description, location_id: Number(form.location_id) || null,
      group_id: form.group_id ? Number(form.group_id) : null,
      start_datetime: new Date(form.start_datetime).toISOString(), end_datetime: new Date(form.end_datetime).toISOString(),
      meeting_point_name: form.meeting_point_name, meeting_latitude: form.meeting?.[0] ?? null, meeting_longitude: form.meeting?.[1] ?? null,
      difficulty: form.difficulty, distance_km: form.distance_km || null, estimated_duration_hours: form.estimated_duration_hours || null,
      min_experience_level: form.min_experience_level, participant_capacity: Number(form.participant_capacity), safety_notes: form.safety_notes,
    };
    try {
      if (editing && existing.data && new Date(existing.data.start_datetime).getTime() === new Date(body.start_datetime).getTime())
        delete body.start_datetime; // unchanged start may already be close; don't re-validate it
      const trip = editing ? await api(`/trips/${id}/`, { method: "PATCH", body }) : await api("/trips/", { method: "POST", body });
      if (!editing) {
        for (const item of equipment.filter((i) => i.item_name.trim()))
          await api(`/trips/${trip.id}/equipment/`, { method: "POST", body: item });
      }
      if (publish && trip.status === "draft") await api(`/trips/${trip.id}/publish/`, { method: "POST" });
      navigate(`/trips/${trip.id}`);
    } catch (err) {
      setErrors(err instanceof ApiError ? { ...Object.fromEntries(Object.keys(err.data || {}).map((k) => [k, err.field(k)])), form: err.message } : { form: err.message });
    } finally { setBusy(false); }
  };

  if (editing && existing.loading) return <Spinner />;
  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <Link to={editing ? `/trips/${id}` : "/trips"} className="btn-ghost -ml-3 mb-2 px-3 py-1.5"><ArrowLeft size={16} /> Back</Link>
      <div className="mb-5 flex flex-wrap items-center gap-3">
        <div className="mr-auto">
          <h1 className="text-2xl font-extrabold">{editing ? "Edit trip" : "Create a camping trip"}</h1>
          <p className="text-ink/60">{editing ? "Participants are notified if you change the dates or meeting point." : "Share your plan and invite others to join."}</p>
        </div>
        {!editing && <button className="btn-outline" disabled={busy} onClick={() => save(false)}>Save as draft</button>}
        <button className="btn-primary" disabled={busy} onClick={() => save(!editing)}>{editing ? "Save changes" : "Publish trip"}</button>
      </div>
      {errors.form && <ErrorNote error={errors.form} className="mb-4" />}

      <form onSubmit={(e) => { e.preventDefault(); save(!editing); }} className="grid gap-5 lg:grid-cols-2">
        <div className="space-y-5">
          <Card title="Basic information">
            <Field label="Trip title" required error={errors.title}><input className="input" required maxLength={200} placeholder="e.g. Khao Yai Weekend Camp" value={form.title} onChange={set("title")} /></Field>
            <Field label="Description" error={errors.description}><textarea className="input" rows={4} placeholder="What's the plan? Who is it for?" value={form.description} onChange={set("description")} /></Field>
            <Field label="Campsite" required error={errors.location_id} hint={<>Can't find it? <Link to="/campsites/new" className="link">Suggest a campsite</Link></>}>
              <select className="input" required value={form.location_id} onChange={set("location_id")}>
                <option value="">Choose a campsite…</option>
                {results(campsites.data).map((c) => <option key={c.id} value={c.id}>{c.name} ({c.province})</option>)}
              </select>
            </Field>
            {(myGroups.data || []).length > 0 && (
              <Field label="Group (optional)" error={errors.group_id} hint="Trips in a private group are only visible to its members.">
                <select className="input" value={form.group_id} onChange={set("group_id")}>
                  <option value="">No group — open to everyone</option>
                  {myGroups.data.map((g) => <option key={g.id} value={g.id}>{g.name}</option>)}
                </select>
              </Field>
            )}
          </Card>
          <Card title="Dates and meeting point">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Start" required error={errors.start_datetime}><input type="datetime-local" className="input" required value={form.start_datetime} onChange={set("start_datetime")} /></Field>
              <Field label="End" required error={errors.end_datetime}><input type="datetime-local" className="input" required value={form.end_datetime} onChange={set("end_datetime")} /></Field>
            </div>
            <Field label="Meeting point name" error={errors.meeting_point_name}><input className="input" placeholder="e.g. Khao Yai Visitor Center" value={form.meeting_point_name} onChange={set("meeting_point_name")} /></Field>
            <div>
              <span className="label">Meeting point on the map</span>
              <PinPicker value={form.meeting} onChange={(p) => setForm({ ...form, meeting: p })} center={site ? [site.latitude, site.longitude] : null} />
              <p className="mt-1 flex justify-between text-xs text-ink/55">
                <span>Click the map to set it. Only confirmed participants see the exact spot.</span>
                {form.meeting && <button type="button" className="link" onClick={() => setForm({ ...form, meeting: null })}>Clear</button>}
              </p>
              {errors.meeting_latitude && <p className="text-xs text-red-700">{errors.meeting_latitude}</p>}
            </div>
          </Card>
        </div>
        <div className="space-y-5">
          <Card title="Trip details">
            <fieldset><legend className="label">Difficulty</legend>
              <div className="flex flex-wrap gap-2">
                {DIFFICULTIES.map((d) => (
                  <label key={d} className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-1.5 text-sm ${form.difficulty === d ? "border-forest-700 bg-forest-50 font-semibold text-forest-800" : "border-slate-300"}`}>
                    <input type="radio" className="accent-forest-700" checked={form.difficulty === d} onChange={() => setForm({ ...form, difficulty: d })} /> {label(d)}
                  </label>
                ))}
              </div>
            </fieldset>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Distance (km)" error={errors.distance_km}><input type="number" min="0" step="0.1" className="input" value={form.distance_km} onChange={set("distance_km")} /></Field>
              <Field label="Estimated duration (hours)" error={errors.estimated_duration_hours}><input type="number" min="0" step="0.5" className="input" value={form.estimated_duration_hours} onChange={set("estimated_duration_hours")} /></Field>
            </div>
            <Field label="Minimum experience level">
              <select className="input" value={form.min_experience_level} onChange={set("min_experience_level")}>
                {LEVELS.map((l) => <option key={l} value={l}>{label(l)}</option>)}
              </select>
            </Field>
          </Card>
          <Card title="Capacity">
            <Field label="Number of spots" required error={errors.participant_capacity} hint="When the trip is full, new people join a waitlist automatically. You don't take a spot yourself.">
              <input type="number" min="1" className="input w-32" required value={form.participant_capacity} onChange={set("participant_capacity")} />
            </Field>
          </Card>
          {!editing && (
            <Card title="Equipment">
              {equipment.map((item, i) => (
                <div key={i} className="grid grid-cols-[1fr_auto_auto] items-center gap-2">
                  <input className="input" placeholder="Item, e.g. Tent (4-person)" value={item.item_name}
                         onChange={(e) => setEquipment(equipment.map((x, j) => (j === i ? { ...x, item_name: e.target.value } : x)))} />
                  <select className="input w-auto" value={item.provided_by} aria-label="Provided by"
                          onChange={(e) => setEquipment(equipment.map((x, j) => (j === i ? { ...x, provided_by: e.target.value } : x)))}>
                    <option value="participant">Bring own</option><option value="organizer">I provide</option>
                  </select>
                  <button type="button" className="btn-ghost p-2" aria-label="Remove item" onClick={() => setEquipment(equipment.filter((_, j) => j !== i))}><Trash2 size={16} /></button>
                </div>
              ))}
              <button type="button" className="btn-outline btn-sm" onClick={() => setEquipment([...equipment, { item_name: "", required: true, provided_by: "participant", notes: "" }])}>
                <Plus size={14} /> Add item</button>
            </Card>
          )}
          <Card title="Safety">
            <Field label="Safety notes"><textarea className="input" rows={3} placeholder="e.g. Watch for wildlife at dusk; bring rain gear." value={form.safety_notes} onChange={set("safety_notes")} /></Field>
          </Card>
        </div>
      </form>
    </div>
  );
}
