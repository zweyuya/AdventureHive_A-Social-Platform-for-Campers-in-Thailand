import { Camera, ShieldCheck, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Avatar, ErrorNote, Field, Modal } from "../components/ui";
import { api, apiUpload } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useApi } from "../lib/hooks";
import { LEVELS, label } from "../lib/format";
import { ReviewItem } from "./CampsiteDetail";

function EmergencyContact({ userId }) {
  const { data, error, reload } = useApi(`/users/${userId}/emergency-contact/`);
  const [form, setForm] = useState({ name: "", phone: "", relationship: "" });
  const [msg, setMsg] = useState(null);
  const [err, setErr] = useState(null);
  useEffect(() => { if (data) setForm({ name: data.name, phone: data.phone, relationship: data.relationship }); }, [data]);
  const save = async (e) => {
    e.preventDefault(); setErr(null);
    try { await api(`/users/${userId}/emergency-contact/`, { method: "PUT", body: form }); setMsg("Emergency contact saved."); reload(); }
    catch (x) { setErr(x); }
  };
  return (
    <section className="card p-5">
      <h2 className="flex items-center gap-2 font-bold"><ShieldCheck size={18} className="text-forest-700" /> Emergency contact</h2>
      <p className="mt-1 text-sm text-ink/60">Stored encrypted. Only you can see it — not other members, organizers or admins.</p>
      {!data && error?.status === 404 && <p className="mt-2 text-sm text-sunrise-600">You haven't added one yet.</p>}
      <form onSubmit={save} className="mt-4 grid gap-3 sm:grid-cols-3">
        <input className="input" required placeholder="Name" aria-label="Contact name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        <input className="input" required placeholder="Phone" aria-label="Contact phone" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
        <input className="input" required placeholder="Relationship" aria-label="Relationship" value={form.relationship} onChange={(e) => setForm({ ...form, relationship: e.target.value })} />
        <div className="sm:col-span-3"><ErrorNote error={err} />{msg && <p className="text-sm text-forest-700">{msg}</p>}
          <button className="btn-outline mt-2">Save emergency contact</button></div>
      </form>
    </section>
  );
}

function DeleteAccount() {
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const [err, setErr] = useState(null);
  const { setUser } = useAuth();
  const navigate = useNavigate();
  const remove = async (e) => {
    e.preventDefault(); setErr(null);
    try { await api("/auth/account/", { method: "DELETE", body: { password } }); setUser(null); navigate("/login"); }
    catch (x) { setErr(x); }
  };
  return (
    <section className="card border-red-200 p-5">
      <h2 className="font-bold text-red-800">Delete account</h2>
      <p className="mt-1 text-sm text-ink/65">Your personal data is erased. Your reviews stay, shown as “Deleted user”. Trips you organise are cancelled.</p>
      <button className="btn-danger mt-3" onClick={() => setOpen(true)}>Delete my account</button>
      {open && (
        <Modal title="Delete your account?" onClose={() => setOpen(false)}>
          <form onSubmit={remove} className="space-y-3">
            <p className="text-sm text-ink/75">This can't be undone. Enter your password to confirm.</p>
            <input type="password" className="input" required autoComplete="current-password" aria-label="Password" value={password} onChange={(e) => setPassword(e.target.value)} />
            <ErrorNote error={err} />
            <button className="btn-danger w-full">Delete account permanently</button>
          </form>
        </Modal>
      )}
    </section>
  );
}

function PhotoPicker({ user, setUser }) {
  const input = useRef(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState(null);
  const upload = async (file) => {
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) return setErr("The photo must be 5 MB or smaller.");
    setBusy(true); setErr(null);
    try {
      const fd = new FormData(); fd.append("avatar", file);
      setUser(await apiUpload("/users/me/avatar/", fd));
    } catch (x) { setErr(x); } finally { setBusy(false); if (input.current) input.current.value = ""; }
  };
  const remove = async () => { setBusy(true); try { setUser(await api("/users/me/avatar/", { method: "DELETE" })); } finally { setBusy(false); } };
  return (
    <div className="flex items-center gap-4">
      <div className="relative">
        <Avatar name={user.display_name} id={user.id} src={user.avatar} size="h-20 w-20 text-2xl" />
        <button type="button" onClick={() => input.current?.click()} disabled={busy}
                className="absolute -bottom-1 -right-1 rounded-full bg-forest-700 p-2 text-white shadow hover:bg-forest-800" aria-label="Change profile photo">
          <Camera size={14} />
        </button>
      </div>
      <div>
        <h1 className="text-2xl font-extrabold">{user.display_name}</h1>
        <p className="text-sm text-ink/60">{user.email} · user ID {user.id}</p>
        <div className="mt-1 flex flex-wrap gap-3 text-sm">
          <button type="button" className="link" onClick={() => input.current?.click()} disabled={busy}>{busy ? "Uploading…" : user.avatar ? "Change photo" : "Add a profile photo"}</button>
          {user.avatar && <button type="button" className="inline-flex items-center gap-1 text-red-700 hover:underline" onClick={remove} disabled={busy}><Trash2 size={13} /> Remove</button>}
        </div>
        <p className="text-xs text-ink/50">JPEG, PNG or WebP up to 5 MB. Location data is removed from your photo.</p>
        <ErrorNote error={err} className="mt-2" />
      </div>
      <input ref={input} type="file" accept="image/jpeg,image/png,image/webp" className="hidden" onChange={(e) => upload(e.target.files?.[0])} />
    </div>
  );
}

export default function Profile() {
  const { user, setUser } = useAuth();
  const tags = useApi("/interest-tags/");
  const reviews = useApi("/reviews/mine/");
  const [form, setForm] = useState({ display_name: user.display_name, bio: user.bio, city: user.city, phone: user.phone || "",
    camping_experience_level: user.camping_experience_level, interest_tag_ids: user.interest_tags.map((t) => t.id) });
  const [msg, setMsg] = useState(null);
  const [err, setErr] = useState(null);
  const save = async (e) => {
    e.preventDefault(); setErr(null); setMsg(null);
    try { setUser(await api(`/users/${user.id}/`, { method: "PATCH", body: form })); setMsg("Profile saved."); }
    catch (x) { setErr(x); }
  };
  const toggle = (id) => setForm((f) => ({ ...f, interest_tag_ids: f.interest_tag_ids.includes(id) ? f.interest_tag_ids.filter((t) => t !== id) : [...f.interest_tag_ids, id] }));
  return (
    <div className="mx-auto max-w-3xl space-y-6 px-4 py-6">
      <PhotoPicker user={user} setUser={setUser} />
      <form onSubmit={save} className="card space-y-4 p-5">
        <h2 className="font-bold">Profile</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Display name"><input className="input" required value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} /></Field>
          <Field label="City"><input className="input" value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} /></Field>
          <Field label="Phone" hint="Never shown on your public profile."><input className="input" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></Field>
          <Field label="Camping experience"><select className="input" value={form.camping_experience_level} onChange={(e) => setForm({ ...form, camping_experience_level: e.target.value })}>
            {LEVELS.map((l) => <option key={l} value={l}>{label(l)}</option>)}</select></Field>
        </div>
        <Field label="About you"><textarea className="input" rows={3} value={form.bio} onChange={(e) => setForm({ ...form, bio: e.target.value })} /></Field>
        <div><span className="label">Interests</span><div className="flex flex-wrap gap-2">
          {(tags.data || []).map((t) => <button type="button" key={t.id} onClick={() => toggle(t.id)} aria-pressed={form.interest_tag_ids.includes(t.id)}
            className={`chip ${form.interest_tag_ids.includes(t.id) ? "chip-on" : ""}`}>{label(t.tag_name)}</button>)}</div></div>
        <ErrorNote error={err} />{msg && <p className="text-sm text-forest-700">{msg}</p>}
        <button className="btn-primary">Save profile</button>
      </form>
      <EmergencyContact userId={user.id} />
      <section id="reviews" className="card p-5">
        <h2 className="font-bold">My reviews</h2>
        {(reviews.data || []).length === 0 && <p className="mt-2 text-sm text-ink/60">You haven't written any reviews yet.</p>}
        {(reviews.data || []).map((r) => <ReviewItem key={r.id} r={r} />)}
      </section>
      <DeleteAccount />
    </div>
  );
}
