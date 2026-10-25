import { ArrowLeft } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { PinPicker, campIcon } from "../components/maps";
import { ErrorNote, Field, Spinner } from "../components/ui";
import { api, ApiError } from "../lib/api";
import { useApi } from "../lib/hooks";
import { CAMPSITE_CATEGORIES, PROVINCES, label } from "../lib/format";

/** New campsite submission, and editing a draft / rejected submission (?id). */
export default function SuggestCampsite() {
  const { id } = useParams();
  const navigate = useNavigate();
  const existing = useApi(id ? `/campsites/${id}/` : null);
  const [form, setForm] = useState({ name: "", province: "", category: "campsite", description: "", pin: null,
    terrain_type: "", has_water_source: false, has_restrooms: false, fire_pit_allowed: false, permit_status: "unknown",
    permit_details: "", rules: "", permit_info_source: "" });
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const c = existing.data; if (!c) return;
    setForm({ ...form, ...Object.fromEntries(Object.keys(form).filter((k) => k in c).map((k) => [k, c[k] ?? ""])), pin: [c.latitude, c.longitude] });
  }, [existing.data]); // eslint-disable-line react-hooks/exhaustive-deps

  const save = async (submit) => {
    if (!form.pin) return setErrors({ pin: "Click the map to place the campsite." });
    setBusy(true); setErrors({});
    const { pin, ...rest } = form;
    const body = { ...rest, latitude: pin[0], longitude: pin[1] };
    try {
      const c = id ? await api(`/campsites/${id}/`, { method: "PATCH", body }) : await api("/campsites/", { method: "POST", body });
      if (submit) await api(`/campsites/${c.id}/submit/`, { method: "POST" });
      navigate("/my/submissions", { state: { flash: submit ? `“${c.name}” was sent for review.` : `Draft “${c.name}” saved.` } });
    } catch (err) {
      setErrors(err instanceof ApiError ? { ...Object.fromEntries(Object.keys(err.data).map((k) => [k, err.field(k)])), form: err.message } : { form: err.message });
    } finally { setBusy(false); }
  };
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  if (id && existing.loading) return <Spinner />;

  return (
    <div className="mx-auto max-w-5xl px-4 py-6">
      <Link to="/campsites" className="btn-ghost -ml-3 mb-2 px-3 py-1.5"><ArrowLeft size={16} /> Campsites</Link>
      <h1 className="text-2xl font-extrabold">{id ? "Edit your submission" : "Suggest a campsite"}</h1>
      <p className="mt-1 max-w-prose text-ink/65">A moderator checks every new campsite before it appears on the map. You'll get a notification when it's approved, or a note explaining what to fix.</p>
      {existing.data?.moderation_note && <p className="mt-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-900"><span className="font-semibold">Moderator note:</span> {existing.data.moderation_note}</p>}
      <form onSubmit={(e) => { e.preventDefault(); save(true); }} className="mt-6 grid gap-6 lg:grid-cols-2">
        <section className="card space-y-4 p-5">
          <Field label="Campsite name" required error={errors.name}><input className="input" required maxLength={200} value={form.name} onChange={set("name")} /></Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Province" required error={errors.province}>
              <input className="input" required list="provinces" value={form.province} onChange={set("province")} />
              <datalist id="provinces">{PROVINCES.map((p) => <option key={p} value={p} />)}</datalist>
            </Field>
            <Field label="Category"><select className="input" value={form.category} onChange={set("category")}>
              {CAMPSITE_CATEGORIES.map((c) => <option key={c} value={c}>{label(c)}</option>)}</select></Field>
          </div>
          <Field label="Description"><textarea className="input" rows={3} value={form.description} onChange={set("description")} /></Field>
          <Field label="Terrain"><input className="input" placeholder="e.g. Pine forest by a lake" value={form.terrain_type} onChange={set("terrain_type")} /></Field>
          <fieldset><legend className="label">Facilities</legend>
            {[["has_water_source", "Water source"], ["has_restrooms", "Restrooms"], ["fire_pit_allowed", "Fire pit allowed"]].map(([k, t]) => (
              <label key={k} className="mr-4 inline-flex items-center gap-2 py-1 text-sm"><input type="checkbox" className="h-4 w-4 accent-forest-700"
                checked={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.checked })} /> {t}</label>
            ))}
          </fieldset>
        </section>
        <section className="card space-y-4 p-5">
          <div>
            <span className="label">Location <span className="text-red-600">*</span></span>
            <PinPicker value={form.pin} onChange={(p) => setForm({ ...form, pin: p })} icon={campIcon} className="h-64" />
            {(errors.pin || errors.latitude || errors.longitude) && <p className="mt-1 text-xs text-red-700">{errors.pin || errors.latitude || errors.longitude}</p>}
            <p className="mt-1 text-xs text-ink/55">Click where the campsite is. It must be inside Thailand.</p>
          </div>
          <Field label="Permit"><select className="input" value={form.permit_status} onChange={set("permit_status")}>
            <option value="unknown">I don't know</option><option value="required">Required</option><option value="not_required">Not required</option></select></Field>
          <Field label="Permit details / rules"><textarea className="input" rows={2} value={form.permit_details} onChange={set("permit_details")} /></Field>
          <Field label="Source of this information" hint="e.g. Park website, phone call to the park office"><input className="input" value={form.permit_info_source} onChange={set("permit_info_source")} /></Field>
        </section>
        <div className="flex flex-wrap gap-3 lg:col-span-2">
          <ErrorNote error={errors.form} className="w-full" />
          <button type="button" className="btn-outline" disabled={busy} onClick={() => save(false)}>Save draft</button>
          <button className="btn-primary" disabled={busy}>Send for review</button>
        </div>
      </form>
    </div>
  );
}
