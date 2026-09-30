import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { mediaUrl } from "../api.js";
import Header from "../components/Header.jsx";

export default function Reports() {
  const [items, setItems] = useState(null);
  const [busyId, setBusyId] = useState(null);

  function load() { api.get("/api/analysis").then((r) => setItems(r.data)); }
  useEffect(load, []);

  async function regen(id) {
    setBusyId(id);
    try {
      await api.post(`/api/analysis/${id}/report`);
      load();
    } finally { setBusyId(null); }
  }

  const withReports = (items || []).filter((a) => a.report_url);

  return (
    <>
      <Header title="Reports" crumb="Downloadable PDF analysis reports" />
      <div className="content">
        {!items ? (
          <div className="center-load"><span className="loader" /></div>
        ) : items.length === 0 ? (
          <div className="card empty">
            <div className="em-ic">▤</div>
            <h3>No reports yet</h3>
            <p style={{ margin: "8px 0 18px" }}>Every analysis generates a PDF report automatically.</p>
            <Link to="/upload" className="btn">Run an analysis</Link>
          </div>
        ) : (
          <div className="card">
            <h3>Generated Reports ({withReports.length})</h3>
            <table className="tbl" style={{ marginTop: 12 }}>
              <thead>
                <tr><th>Scene</th><th>Confidence</th><th>Generated</th><th>Report</th></tr>
              </thead>
              <tbody>
                {items.map((a) => (
                  <tr key={a.id}>
                    <td>
                      <Link to={`/analyses/${a.id}`} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                        <img src={mediaUrl(a.segmentation_url)} alt="" style={{ width: 34, height: 34, borderRadius: 7, objectFit: "cover" }} />
                        <b>{a.name}</b>
                      </Link>
                    </td>
                    <td>{a.confidence}%</td>
                    <td style={{ color: "var(--muted)", fontSize: 12 }}>{a.created_at?.slice(0, 16)}</td>
                    <td>
                      {a.report_url ? (
                        <a className="btn ghost sm" href={mediaUrl(a.report_url)} target="_blank" rel="noreferrer">▤ Download PDF</a>
                      ) : (
                        <button className="btn sm" onClick={() => regen(a.id)} disabled={busyId === a.id}>
                          {busyId === a.id ? "Generating…" : "Generate"}
                        </button>
                      )}
                    </td>
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
