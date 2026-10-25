import { ArrowLeft, Mail, User } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Logo from "../components/Logo";
import { ErrorNote } from "../components/ui";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { LEVELS, label } from "../lib/format";
import AuthLayout from "./AuthLayout";
import { IconInput, PasswordInput } from "./Login";

export default function Register() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [tags, setTags] = useState([]);
  const [form, setForm] = useState({ display_name: "", email: "", password: "", confirm: "",
                                      camping_experience_level: "beginner", interest_tag_ids: [], pdpa_consent: false });
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);
  useEffect(() => { api("/interest-tags/").then(setTags).catch(() => {}); }, []);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const toggleTag = (id) => setForm((f) => ({ ...f, interest_tag_ids: f.interest_tag_ids.includes(id)
    ? f.interest_tag_ids.filter((t) => t !== id) : [...f.interest_tag_ids, id] }));

  const submit = async (e) => {
    e.preventDefault();
    if (form.password !== form.confirm) return setErrors({ confirm: "The passwords don't match." });
    if (!form.pdpa_consent) return setErrors({ pdpa_consent: "Please agree to the privacy policy to create an account." });
    setBusy(true); setErrors({});
    try {
      const { confirm, ...body } = form; // eslint-disable-line no-unused-vars
      await api("/auth/register/", { method: "POST", body });
      await login(form.email, form.password);
      navigate("/", { replace: true });
    } catch (err) {
      setErrors(err instanceof ApiError
        ? { email: err.field("email"), password: err.field("password"), pdpa_consent: err.field("pdpa_consent"),
            form: err.field("email") || err.field("password") ? null : err.message }
        : { form: err.message });
    } finally { setBusy(false); }
  };

  const fieldError = (k) => errors[k] && <span className="mt-1 block text-xs text-red-700">{errors[k]}</span>;
  return (
    <AuthLayout>
      <Link to="/login" className="btn-ghost -ml-3 mb-2 p-2" aria-label="Back to log in"><ArrowLeft size={20} /></Link>
      <Logo stacked tagline={false} />
      <h1 className="mt-8 text-center text-2xl font-extrabold">Create your account</h1>
      <p className="mt-1 text-center text-ink/60">Join Thailand's camping community.</p>
      <form onSubmit={submit} className="mt-6 space-y-4" noValidate>
        <IconInput icon={User} required placeholder="Display name" aria-label="Display name" value={form.display_name} onChange={set("display_name")} />
        <div><IconInput icon={Mail} type="email" required placeholder="Email address" aria-label="Email address" value={form.email} onChange={set("email")} />{fieldError("email")}</div>
        <div><PasswordInput required autoComplete="new-password" placeholder="Password (at least 8 characters)" aria-label="Password" value={form.password} onChange={set("password")} />{fieldError("password")}</div>
        <div><PasswordInput required autoComplete="new-password" placeholder="Confirm password" aria-label="Confirm password" value={form.confirm} onChange={set("confirm")} />{fieldError("confirm")}</div>

        <fieldset>
          <legend className="label">Camping experience</legend>
          <div className="grid grid-cols-2 gap-2">
            {LEVELS.map((lvl) => (
              <label key={lvl} className={`flex cursor-pointer items-center gap-2 rounded-lg border px-3 py-2 text-sm ${form.camping_experience_level === lvl ? "border-forest-700 bg-forest-50 font-semibold text-forest-800" : "border-slate-300"}`}>
                <input type="radio" name="level" value={lvl} checked={form.camping_experience_level === lvl}
                       onChange={set("camping_experience_level")} className="accent-forest-700" />
                {label(lvl)}
              </label>
            ))}
          </div>
          <p className="mt-1 text-xs text-ink/55">Some trips ask for a minimum level.</p>
        </fieldset>

        <fieldset>
          <legend className="label">Interests <span className="font-normal text-ink/55">(pick a few)</span></legend>
          <div className="flex flex-wrap gap-2">
            {tags.map((t) => (
              <button type="button" key={t.id} onClick={() => toggleTag(t.id)} aria-pressed={form.interest_tag_ids.includes(t.id)}
                      className={`chip ${form.interest_tag_ids.includes(t.id) ? "chip-on" : ""}`}>{label(t.tag_name)}</button>
            ))}
          </div>
        </fieldset>

        <div>
          <label className="flex items-start gap-3 text-sm">
            <input type="checkbox" checked={form.pdpa_consent} onChange={(e) => setForm({ ...form, pdpa_consent: e.target.checked })}
                   className="mt-0.5 h-4 w-4 accent-forest-700" />
            <span>I agree to the collection and use of my personal data as described in the{" "}
              <Link to="/privacy" target="_blank" className="link">privacy policy (PDPA)</Link>.</span>
          </label>
          {fieldError("pdpa_consent")}
        </div>
        <ErrorNote error={errors.form} />
        <button className="btn-primary w-full py-3 text-base" disabled={busy}>{busy ? "Creating account…" : "Create account"}</button>
      </form>
      <p className="mt-6 text-center text-sm text-ink/70">Already have an account? <Link to="/login" className="link">Log in</Link></p>
    </AuthLayout>
  );
}
