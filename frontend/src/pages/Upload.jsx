import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import api, { mediaUrl } from "../api.js";
import Header from "../components/Header.jsx";
import AnalysisResult from "../components/AnalysisResult.jsx";

export default function Upload() {
  const inputRef = useRef();
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [meta, setMeta] = useState({ name: "", lat: "", lon: "", clusters: 6 });
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [err, setErr] = useState("");

  function pick(f) {
    if (!f) return;
    setFile(f);
    setPreview(URL.createObjectURL(f));
    setMeta((m) => ({ ...m, name: m.name || f.name }));
    setResult(null);
    setErr("");
  }

  function onDrop(e) {
    e.preventDefault();
    setDrag(false);
    pick(e.dataTransfer.files?.[0]);
  }

  async function analyze() {
    if (!file) return;
    setBusy(true);
    setErr("");
    try {
      const fd = new FormData();
      fd.append("file", file);
      if (meta.name) fd.append("name", meta.name);
      if (meta.lat) fd.append("lat", meta.lat);
      if (meta.lon) fd.append("lon", meta.lon);
      if (meta.clusters) fd.append("clusters", meta.clusters);
      const r = await api.post("/api/analysis", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setResult(r.data);
    } catch (ex) {
      setErr(ex?.response?.data?.detail || "Analysis failed. Try another image.");
    } finally {
      setBusy(false);
    }
  }

  function reset() {
    setFile(null); setPreview(null); setResult(null); setErr("");
    setMeta({ name: "", lat: "", lon: "", clusters: 6 });
  }

  return (
    <>
      <Header title="Upload &amp; Analyse" crumb="Run the full AI pipeline on a satellite image" />
      <div className="content">
        {!result && (
          <div className="grid cards-2">
            <div className="card">
              <h3>Satellite Image</h3>
              <div className="card-sub">JPG, PNG, WEBP, TIFF or BMP</div>
              <div
                className={`dropzone ${drag ? "drag" : ""}`}
                onClick={() => inputRef.current.click()}
                onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
                onDragLeave={() => setDrag(false)}
                onDrop={onDrop}
              >
                {preview ? (
                  <img src={preview} alt="preview" className="preview-img" style={{ maxHeight: 260 }} />
                ) : (
                  <>
                    <div className="dz-ic">🛰️</div>
                    <h4>Drop an image here</h4>
                    <p>or click to browse your files</p>
                  </>
                )}
              </div>
              <input
                ref={inputRef}
                type="file"
                accept="image/*"
                hidden
                onChange={(e) => pick(e.target.files?.[0])}
              />
              {file && <p style={{ marginTop: 10, fontSize: 12.5, color: "var(--muted)" }}>Selected: <b>{file.name}</b></p>}
            </div>

            <div className="card">
              <h3>Analysis Options</h3>
              <div className="card-sub">Optional metadata &amp; parameters</div>
              <div className="field">
                <label>Scene name</label>
                <input value={meta.name} onChange={(e) => setMeta({ ...meta, name: e.target.value })} placeholder="e.g. Ghaziabad_2026" />
              </div>
              <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div className="field">
                  <label>Latitude</label>
                  <input value={meta.lat} onChange={(e) => setMeta({ ...meta, lat: e.target.value })} placeholder="28.67" />
                </div>
                <div className="field">
                  <label>Longitude</label>
                  <input value={meta.lon} onChange={(e) => setMeta({ ...meta, lon: e.target.value })} placeholder="77.45" />
                </div>
              </div>
              <div className="field">
                <label>Segmentation detail (clusters): {meta.clusters}</label>
                <input type="range" min="4" max="10" value={meta.clusters}
                  onChange={(e) => setMeta({ ...meta, clusters: e.target.value })}
                  style={{ width: "100%" }} />
              </div>

              {err && <div className="err">{err}</div>}

              <div className="wrap-actions" style={{ marginTop: 8 }}>
                <button className="btn" onClick={analyze} disabled={!file || busy}>
                  {busy ? "Analysing…" : "⚡ Run Analysis"}
                </button>
                {file && <button className="btn ghost" onClick={reset} disabled={busy}>Clear</button>}
              </div>
              {busy && <p style={{ marginTop: 12, fontSize: 12.5, color: "var(--muted)" }}>
                Running preprocessing → segmentation → detection → report…
              </p>}
            </div>
          </div>
        )}

        {result && (
          <>
            <div className="card flex between center" style={{ marginBottom: 20 }}>
              <div>
                <h3 style={{ margin: 0 }}>✓ Analysis complete — {result.name}</h3>
                <div className="card-sub" style={{ margin: "4px 0 0" }}>Confidence {result.confidence}% · {result.width}×{result.height}px</div>
              </div>
              <div className="wrap-actions">
                {result.report_url && (
                  <a className="btn ghost" href={mediaUrl(result.report_url)} target="_blank" rel="noreferrer">▤ Download PDF</a>
                )}
                <Link className="btn ghost" to={`/analyses/${result.id}`}>Open detail</Link>
                <button className="btn" onClick={reset}>+ New analysis</button>
              </div>
            </div>
            <AnalysisResult a={result} />
          </>
        )}
      </div>
    </>
  );
}
