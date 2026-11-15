import { Field } from "./ui";
import { useApi } from "../lib/hooks";

/** Permit, fees and rules inputs. Shared by "Suggest a campsite" and "Suggest an edit". */
export default function PermitFields({ form, setForm, errors, sourceLabel = "Source of this information" }) {
  const authorities = useApi("/authorities/");
  // errors: a plain {field: message} object, or an ApiError from the server
  const err = (k) => (errors?.field ? errors.field(k) : errors?.[k]);
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  return (
    <div className="space-y-4">
      <div>
        <h2 className="font-bold text-navy-900">Permit, fees and rules</h2>
        <p className="text-xs text-ink/60">Campers rely on this to plan. Add only what you know, and say where it came from.</p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Permit" error={err("permit_status")}>
          <select className="input" value={form.permit_status} onChange={set("permit_status")}>
            <option value="unknown">I don't know</option><option value="required">Required</option>
            <option value="not_required">Not required</option>
          </select>
        </Field>
        <Field label="Managed by" error={err("authority_id")} hint="Phone and website come from the park's record.">
          <select className="input" value={form.authority_id ?? ""} onChange={set("authority_id")}>
            <option value="">Not sure / not listed</option>
            {(authorities.data || []).map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
        </Field>
      </div>
      <Field label="Fees" error={err("fees")} hint={'Entry, camping and rental fees, separated by "·" or new lines. Write "Free" if there are none.'}>
        <input className="input" maxLength={300} placeholder="e.g. Entry 100 THB/person · Camping 30 THB/person/night"
               value={form.fees} onChange={set("fees")} />
      </Field>
      <Field label="Permit details" error={err("permit_details")} hint="What permit, where to get it, how far ahead, and the open season.">
        <textarea className="input" rows={2} placeholder="e.g. Register at the park office on arrival. Closed June–October."
                  value={form.permit_details} onChange={set("permit_details")} />
      </Field>
      <Field label="Rules" error={err("rules")} hint="One rule per line.">
        <textarea className="input" rows={3} placeholder={"e.g. No fires outside the fire pits\nQuiet after 22:00"}
                  value={form.rules} onChange={set("rules")} />
      </Field>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Booking link" error={err("permit_booking_url")} hint="Optional">
          <input className="input" type="url" placeholder="https://…" value={form.permit_booking_url} onChange={set("permit_booking_url")} />
        </Field>
        <Field label={sourceLabel} error={err("permit_info_source")} hint="e.g. Park website, phone call to the park office">
          <input className="input" maxLength={200} value={form.permit_info_source} onChange={set("permit_info_source")} />
        </Field>
      </div>
    </div>
  );
}

/** Body values for the API: an empty "Managed by" means none. */
export const permitBody = (form) => ({ ...form, authority_id: form.authority_id ? Number(form.authority_id) : null });
