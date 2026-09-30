import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../auth.jsx";

export default function Login() {
  const { login, register } = useAuth();
  const nav = useNavigate();
  const [mode, setMode] = useState("login");
  const [form, setForm] = useState({ name: "", email: "demo@bhudarpan.ai", password: "demo1234" });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const upd = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setErr("");
    setBusy(true);
    try {
      if (mode === "login") await login(form.email, form.password);
      else await register(form.name, form.email, form.password);
      nav("/");
    } catch (ex) {
      setErr(ex?.response?.data?.detail || "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-wrap">
      <div className="auth-hero">
        <div className="badge">🛰️ AI Satellite Intelligence</div>
        <h1>Bhū-Darpan</h1>
        <p>
          Automatically analyse satellite imagery — land-cover segmentation, object
          detection, change monitoring and instant PDF reports, all in one dashboard.
        </p>
        <div className="feats">
          <div>◎ Land-cover segmentation into 5 classes</div>
          <div>⊹ Building, road, water &amp; vegetation detection</div>
          <div>⇄ Before/after change detection</div>
          <div>▤ Downloadable analysis reports</div>
        </div>
      </div>

      <div className="auth-form-side">
        <form className="auth-card" onSubmit={submit}>
          <h2>{mode === "login" ? "Welcome back" : "Create account"}</h2>
          <div className="sub">
            {mode === "login" ? "Sign in to your analysis workspace" : "Start analysing satellite imagery"}
          </div>

          {err && <div className="err">{err}</div>}

          {mode === "register" && (
            <div className="field">
              <label>Full name</label>
              <input value={form.name} onChange={upd("name")} placeholder="Your name" required />
            </div>
          )}
          <div className="field">
            <label>Email</label>
            <input type="email" value={form.email} onChange={upd("email")} placeholder="you@email.com" required />
          </div>
          <div className="field">
            <label>Password</label>
            <input type="password" value={form.password} onChange={upd("password")} placeholder="••••••••" required minLength={6} />
          </div>

          <button className="btn" style={{ width: "100%", justifyContent: "center" }} disabled={busy}>
            {busy ? "Please wait…" : mode === "login" ? "Sign in" : "Create account"}
          </button>

          {mode === "login" && (
            <div className="demo-hint">
              <b>Demo login</b> — email <code>demo@bhudarpan.ai</code>, password <code>demo1234</code> (pre-filled).
            </div>
          )}

          <div className="switch-auth">
            {mode === "login" ? (
              <>New here? <b onClick={() => setMode("register")}>Create an account</b></>
            ) : (
              <>Already registered? <b onClick={() => setMode("login")}>Sign in</b></>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}
