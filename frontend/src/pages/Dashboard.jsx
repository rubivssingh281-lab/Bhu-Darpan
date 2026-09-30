import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { mediaUrl } from "../api.js";
import Header from "../components/Header.jsx";
import MapView from "../components/MapView.jsx";
import {
  LandCoverDonut, AreaChangeBar, ConfidenceLine, ObjectsBar,
} from "../components/charts.jsx";

const CLASS_HEX = {
  Forest: "#2E7D32", Water: "#1565C0", Agriculture: "#FBC02D",
  Urban: "#E53935", Others: "#9E9E9E",
};

function Delta({ v }) {
  const cls = v > 0.05 ? "up" : v < -0.05 ? "down" : "flat";
  const arrow = v > 0.05 ? "▲" : v < -0.05 ? "▼" : "▬";
  return <span className={`st-delta ${cls}`}>{arrow} {Math.abs(v).toFixed(1)}% vs prev</span>;
}

function StatCard({ icon, color, label, value, delta }) {
  return (
    <div className="card stat">
      <div className="st-top">
        <span className="st-label">{label}</span>
        <span className="st-ic" style={{ background: color }}>{icon}</span>
      </div>
      <div className="st-value">{value}</div>
      {delta !== undefined && <Delta v={delta} />}
    </div>
  );
}

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [points, setPoints] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.get("/api/dashboard"), api.get("/api/analysis")])
      .then(([d, a]) => {
        setData(d.data);
        setPoints(a.data);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <><Header title="Dashboard" /><div className="center-load"><span className="loader" /></div></>;

  const t = data.totals;
  const lc = data.land_cover;
  const dl = data.land_cover_delta;
  const empty = t.images === 0;

  return (
    <>
      <Header
        title="Dashboard Overview"
        crumb="Live statistics from your satellite image analyses"
        right={<span className={`db-pill ${data.backend.backend === "mongodb" ? "" : "json"}`}>
          ● {data.backend.backend === "mongodb" ? "MongoDB" : "Local store"}
        </span>}
      />
      <div className="content">
        {empty ? (
          <div className="card empty">
            <div className="em-ic">🛰️</div>
            <h3>No analyses yet</h3>
            <p style={{ margin: "8px 0 18px" }}>Upload your first satellite image to see live statistics here.</p>
            <Link to="/upload" className="btn" style={{ textDecoration: "none" }}>☁ Upload an image</Link>
          </div>
        ) : (
          <>
            <div className="grid cards-4">
              <StatCard icon="🛰️" color="#1565C0" label="Total Images Processed" value={t.images} />
              <StatCard icon="🌳" color="#2E7D32" label="Forest Area" value={`${lc.Forest.toFixed(1)}%`} delta={dl.Forest} />
              <StatCard icon="💧" color="#2AA7FF" label="Water Bodies" value={`${lc.Water.toFixed(1)}%`} delta={dl.Water} />
              <StatCard icon="🏙️" color="#E53935" label="Urban Area" value={`${lc.Urban.toFixed(1)}%`} delta={dl.Urban} />
            </div>

            <div className="grid cards-2" style={{ marginTop: 20 }}>
              <div className="card">
                <h3>Land Cover Distribution</h3>
                <div className="card-sub">Average composition across all analysed scenes</div>
                <div style={{ height: 260 }}><LandCoverDonut data={lc} /></div>
              </div>
              <div className="card">
                <h3>Area Change</h3>
                <div className="card-sub">Recent scenes vs earlier scenes (Δ %)</div>
                <div style={{ height: 260 }}><AreaChangeBar deltas={dl} /></div>
              </div>
            </div>

            <div className="grid cards-2" style={{ marginTop: 20 }}>
              <div className="card">
                <h3>Detected Objects</h3>
                <div className="card-sub">Total detections across all scenes ({t.objects})</div>
                <div style={{ height: 240 }}>
                  {Object.keys(data.object_totals).length
                    ? <ObjectsBar counts={data.object_totals} />
                    : <div className="empty">No objects detected yet</div>}
                </div>
              </div>
              <div className="card">
                <h3>Model Confidence Trend</h3>
                <div className="card-sub">Average confidence: {data.avg_confidence}%</div>
                <div style={{ height: 240 }}><ConfidenceLine trend={data.trend} /></div>
              </div>
            </div>

            <div className="grid cards-2" style={{ marginTop: 20 }}>
              <div className="card">
                <div className="flex between center" style={{ marginBottom: 12 }}>
                  <h3 style={{ margin: 0 }}>Recent Analyses</h3>
                  <Link to="/analyses" className="btn ghost sm">View all</Link>
                </div>
                <table className="tbl">
                  <thead>
                    <tr><th>Scene</th><th>Dominant</th><th>Confidence</th><th>Date</th></tr>
                  </thead>
                  <tbody>
                    {data.recent.map((r) => (
                      <tr key={r.id}>
                        <td>
                          <Link to={`/analyses/${r.id}`} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                            <img src={mediaUrl(r.thumb)} alt="" style={{ width: 34, height: 34, borderRadius: 7, objectFit: "cover" }} />
                            <b>{r.name}</b>
                          </Link>
                        </td>
                        <td><span className="tag" style={{ background: (CLASS_HEX[r.dominant] || "#999") + "22", color: CLASS_HEX[r.dominant] || "#666" }}>{r.dominant}</span></td>
                        <td>{r.confidence}%</td>
                        <td style={{ color: "var(--muted)", fontSize: 12 }}>{r.created_at?.slice(0, 10)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="card">
                <h3>Scene Locations</h3>
                <div className="card-sub">Geotagged analyses</div>
                <MapView points={points} />
              </div>
            </div>
          </>
        )}
      </div>
    </>
  );
}
