import { useEffect, useState } from "react";
import api from "../api.js";
import Header from "../components/Header.jsx";
import { useAuth } from "../auth.jsx";

const CLASSES = [
  ["Forest", "#2E7D32"], ["Water", "#1565C0"], ["Agriculture", "#FBC02D"],
  ["Urban", "#E53935"], ["Others", "#9E9E9E"],
];

export default function Settings() {
  const { user } = useAuth();
  const [health, setHealth] = useState(null);
  const [clusters, setClusters] = useState(Number(localStorage.getItem("bd_clusters") || 6));
  const [saved, setSaved] = useState(false);

  useEffect(() => { api.get("/api/health").then((r) => setHealth(r.data)).catch(() => {}); }, []);

  function save() {
    localStorage.setItem("bd_clusters", clusters);
    setSaved(true);
    setTimeout(() => setSaved(false), 1500);
  }

  return (
    <>
      <Header title="Settings" crumb="Account, engine &amp; preferences" />
      <div className="content">
        <div className="grid cards-2">
          <div className="card">
            <h3>Account</h3>
            <div className="card-sub">Your profile</div>
            <table className="tbl">
              <tbody>
                <tr><td style={{ color: "var(--muted)" }}>Name</td><td><b>{user?.name}</b></td></tr>
                <tr><td style={{ color: "var(--muted)" }}>Email</td><td>{user?.email}</td></tr>
                <tr><td style={{ color: "var(--muted)" }}>Member since</td><td>{user?.created_at?.slice(0, 10)}</td></tr>
              </tbody>
            </table>
          </div>

          <div className="card">
            <h3>System Status</h3>
            <div className="card-sub">Backend &amp; database</div>
            {health ? (
              <table className="tbl">
                <tbody>
                  <tr><td style={{ color: "var(--muted)" }}>API status</td><td><span className="tag" style={{ background: "#e8f5ee", color: "#2E7D32" }}>{health.status}</span></td></tr>
                  <tr><td style={{ color: "var(--muted)" }}>Version</td><td>{health.version}</td></tr>
                  <tr><td style={{ color: "var(--muted)" }}>Database</td><td><b>{health.database.backend}</b></td></tr>
                  <tr><td style={{ color: "var(--muted)" }}>DB name</td><td>{health.database.db_name}</td></tr>
                </tbody>
              </table>
            ) : <p style={{ color: "var(--muted)" }}>Unable to reach API.</p>}
          </div>
        </div>

        <div className="grid cards-2" style={{ marginTop: 20 }}>
          <div className="card">
            <h3>Analysis Preferences</h3>
            <div className="card-sub">Default segmentation detail used on the Upload page</div>
            <div className="field">
              <label>Segmentation clusters: {clusters}</label>
              <input type="range" min="4" max="10" value={clusters}
                onChange={(e) => setClusters(Number(e.target.value))} style={{ width: "100%" }} />
            </div>
            <button className="btn" onClick={save}>{saved ? "✓ Saved" : "Save preferences"}</button>
          </div>

          <div className="card">
            <h3>Land-Cover Classes</h3>
            <div className="card-sub">Legend used across the platform</div>
            <div className="legend">
              {CLASSES.map(([name, color]) => (
                <div className="lg" key={name}><span className="sw" style={{ background: color }} />{name}</div>
              ))}
            </div>
            <p style={{ marginTop: 16, fontSize: 12.5, color: "var(--muted)", lineHeight: 1.6 }}>
              Bhū-Darpan uses unsupervised K-Means segmentation with rule-based class
              mapping, connected-component object detection, and CIELAB change detection —
              running fully on CPU with no pre-trained weights required.
            </p>
          </div>
        </div>
      </div>
    </>
  );
}
