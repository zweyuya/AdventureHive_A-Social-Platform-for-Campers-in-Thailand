import { Eye, EyeOff, Lock, Mail } from "lucide-react";
import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import Logo from "../components/Logo";
import { ErrorNote } from "../components/ui";
import { useAuth } from "../lib/auth";
import AuthLayout from "./AuthLayout";

export function IconInput({ icon: Icon, right, ...props }) {
  return (
    <div className="relative">
      <Icon size={18} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink/45" />
      <input className="input pl-10 pr-10" {...props} />
      {right && <div className="absolute right-2 top-1/2 -translate-y-1/2">{right}</div>}
    </div>
  );
}

export function PasswordInput(props) {
  const [show, setShow] = useState(false);
  return (
    <IconInput icon={Lock} type={show ? "text" : "password"} {...props}
      right={<button type="button" onClick={() => setShow((s) => !s)} className="p-1 text-ink/50 hover:text-ink"
                     aria-label={show ? "Hide password" : "Show password"}>{show ? <EyeOff size={18} /> : <Eye size={18} />}</button>} />
  );
}

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      await login(form.email, form.password);
      navigate(location.state?.from || "/", { replace: true });
    } catch (err) {
      setError(err.status === 429 ? "Too many attempts. Wait a minute and try again." : err.message);
    } finally { setBusy(false); }
  };

  return (
    <AuthLayout>
      <Logo stacked />
      <h1 className="mt-10 text-2xl font-extrabold">Welcome back</h1>
      <p className="mt-1 text-ink/60">Log in to continue your adventure.</p>
      <form onSubmit={submit} className="mt-6 space-y-4">
        <IconInput icon={Mail} type="email" required autoComplete="email" placeholder="Email address" aria-label="Email address"
                   value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
        <PasswordInput required autoComplete="current-password" placeholder="Password" aria-label="Password"
                       value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
        <ErrorNote error={error} />
        <button className="btn-primary w-full py-3 text-base" disabled={busy}>{busy ? "Logging in…" : "Log in"}</button>
      </form>
      <p className="mt-8 text-center text-sm text-ink/70">Don't have an account? <Link to="/register" className="link">Sign up</Link></p>
      <p className="mt-2 text-center text-sm"><Link to="/campsites" className="text-ink/60 hover:text-forest-800">Browse campsites without an account</Link></p>
    </AuthLayout>
  );
}
