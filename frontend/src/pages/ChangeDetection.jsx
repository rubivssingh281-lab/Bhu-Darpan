import { useEffect, useRef, useState } from "react";
import api, { mediaUrl } from "../api.js";
import Header from "../components/Header.jsx";
import { AreaChangeBar } from "../components/charts.jsx";

function ImgPick({ label, file, preview, onPick }) {
  const ref = useRef();
  return (
    <div>
      <label style={{ fontSize: 12.5, fontWeight: 600, color: "#33465c" }}>{label}</label>
      <div className="dropzone" style={{ marginTop: 6, padding: preview ? 10 : 30 }}
        onClick={() => ref.current.click()}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => { e.preventDefault(); onPick(e.dataTransfer.files?.[0]); }}
      >
        {preview ? <img src={preview} className="preview-img" style={{ maxHeight: 180 }} alt={label} />
          : <><div className="dz-ic" style={{ fontSize: 30 }}>🖼️</div><p>Click or drop {label.toLowerCase()}</p></>}
      </div>
      <input ref={ref} type="file" accept="image/*" hidden onChange={(e) => onPick(e.target.files?.[0])} />
      {file && <p style={{ fontSize: 12, color: "var(--muted)", marginTop: 6 }}>{file.name}</p>}
    </div>
  );
}

export default function ChangeDetection() {
  const [before, setBefore] = useState(null);
  const [after, setAfter] = useState(null);
  const [bp, setBp] = useState(null);
  const [ap, setAp] = useState(null);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState(null);
  const [err, setErr] = useState("");
  const [history, setHistory] = useState([]);

  useEffect(() => { api.get("/api/change").then((r) => setHistory(r.data)); }, [res]);

  function pickBefore(f) { if (f) { setBefore(f); setBp(URL.createObjectURL(f)); } }
  function pickAfter(f) { if (f) { setAfter(f); setAp(URL.createObjectURL(f)); } }

  async function run() {
    if (!before || !after) return;
    setBusy(true); setErr("");
    try {
      const fd = new FormData();
      fd.append("before", before);
      fd.append("after", after);
      if (name) fd.append("name", name);
      const r = await api.post("/api/change", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setRes(r.data);
    } catch (ex) {
      setErr(ex?.response?.data?.detail || "Change detection failed.");
    } finally { setBusy(false); }
  }

  function reset() { setBefore(null); setAfter(null); setBp(null); setAp(null); setRes(null); setName(""); }

  return (
    <>
      <Header title="Change Detection" crumb="Compare two images of the same area across time" />
      <div className="content">
        <div className="card">
          <h3>Before / After Comparison</h3>
          <div className="card-sub">Upload two co-located satellite images captured at different times</div>
          <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", gap: 18 }}>
            <ImgPick label="Before" file={before} preview={bp} onPick={pickBefore} />
            <ImgPick label="After" file={after} preview={ap} onPick={pickAfter} />
          </div>
          <div className="field" style={{ marginTop: 16, maxWidth: 340 }}>
            <label>Analysis name</label>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Deforestation_2020_2026" />
          </div>
          {err && <div className="err">{err}</div>}
          <div className="wrap-actions">
            <button className="btn" onClick={run} disabled={!before || !after || busy}>
              {busy ? "Detecting changes…" : "⇄ Detect Changes"}
            </button>
            {(before || after) && <button className="btn ghost" onClick={reset} disabled={busy}>Clear</button>}
          </div>
        </div>

        {res && (
          <>
            <div className="grid cards-3" style={{ marginTop: 20 }}>
              <div className="img-frame"><img src={mediaUrl(res.before_url)} alt="before" /><div className="cap">Before</div></div>
              <div className="img-frame"><img src={mediaUrl(res.after_url)} alt="after" /><div className="cap">After</div></div>
              <div className="img-frame"><img src={mediaUrl(res.change_map_url)} alt="change" /><div className="cap">Change map (red = changed)</div></div>
            </div>
            <div className="grid cards-2" style={{ marginTop: 20 }}>
              <div className="card" style={{ display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center" }}>
                <div className="st-label">Changed Area</div>
                <div style={{ fontFamily: "var(--display)", fontSize: 56, fontWeight: 700, color: "#E53935" }}>{res.changed_percent}%</div>
                <div style={{ fontSize: 12.5, color: "var(--muted)" }}>of the scene changed · confidence {res.confidence}%</div>
                <div className="legend" style={{ marginTop: 16 }}>
                  <div className="lg"><span className="sw" style={{ background: "#E53935" }} />Changed</div>
                  <div className="lg"><span className="sw" style={{ background: "#2E7D32" }} />No change</div>
                </div>
              </div>
              <div className="card">
                <h3>Land-Cover Shift</h3>
                <div className="card-sub">Change in each class (after − before)</div>
                <div style={{ height: 230 }}><AreaChangeBar deltas={res.class_deltas} /></div>
              </div>
            </div>
          </>
        )}

        {history.length > 0 && (
          <div className="card" style={{ marginTop: 20 }}>
            <h3>Previous Change Analyses</h3>
            <table className="tbl" style={{ marginTop: 10 }}>
              <thead><tr><th>Name</th><th>Changed %</th><th>Confidence</th><th>Date</th></tr></thead>
              <tbody>
                {history.map((h) => (
                  <tr key={h.id}>
                    <td><b>{h.name}</b></td>
                    <td><span className="tag" style={{ background: "#fdecea", color: "#c62828" }}>{h.changed_percent}%</span></td>
                    <td>{h.confidence}%</td>
                    <td style={{ color: "var(--muted)", fontSize: 12 }}>{h.created_at?.slice(0, 16)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
