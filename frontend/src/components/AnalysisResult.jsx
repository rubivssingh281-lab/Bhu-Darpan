import { mediaUrl } from "../api.js";
import { LandCoverDonut } from "./charts.jsx";

const CLASS_HEX = {
  Forest: "#2E7D32", Water: "#1565C0", Agriculture: "#FBC02D",
  Urban: "#E53935", Others: "#9E9E9E",
};
const OBJ_COLOR = {
  Building: "#E53935", Road: "#F59E00", "Water Body": "#1565C0",
  Vegetation: "#2E7D32", Farmland: "#8a9a2a",
};

function Frame({ src, cap }) {
  return (
    <div className="img-frame">
      <img src={mediaUrl(src)} alt={cap} />
      <div className="cap">{cap}</div>
    </div>
  );
}

export default function AnalysisResult({ a }) {
  const objectCounts = a.object_counts || {};
  return (
    <>
      <div className="grid cards-3">
        <Frame src={a.original_url} cap="Original (preprocessed)" />
        <Frame src={a.segmentation_url} cap="Land-cover segmentation" />
        <Frame src={a.detection_url} cap="Object detection" />
      </div>

      <div className="grid cards-2" style={{ marginTop: 20 }}>
        <div className="card">
          <h3>Land Cover Distribution</h3>
          <div className="card-sub">{a.width} × {a.height} px · classified into 5 classes</div>
          <div style={{ height: 240 }}><LandCoverDonut data={a.land_cover} /></div>
          <div className="legend" style={{ marginTop: 14 }}>
            {Object.entries(a.land_cover).map(([k, v]) => (
              <div className="lg" key={k}>
                <span className="sw" style={{ background: CLASS_HEX[k] }} />
                {k} — <b>{v.toFixed(1)}%</b>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <h3>Detected Objects</h3>
          <div className="card-sub">{a.objects?.length || 0} detections</div>
          <div className="legend" style={{ marginBottom: 16 }}>
            {Object.entries(objectCounts).map(([k, v]) => (
              <div className="lg" key={k}>
                <span className="sw" style={{ background: OBJ_COLOR[k] || "#666" }} />
                {k} <span className="chip" style={{ marginLeft: 4 }}>{v}</span>
              </div>
            ))}
            {!Object.keys(objectCounts).length && <span style={{ color: "var(--muted)" }}>No discrete objects detected.</span>}
          </div>

          <div style={{ marginTop: 8 }}>
            <div className="flex between" style={{ marginBottom: 6, fontSize: 13 }}>
              <b>Model Confidence</b><b>{a.confidence}%</b>
            </div>
            <div className="conf-bar"><i style={{ width: `${a.confidence}%` }} /></div>
          </div>

          {a.location && a.location.lat != null && (
            <div style={{ marginTop: 16, fontSize: 12.5, color: "var(--muted)" }}>
              📍 Location: {a.location.lat}, {a.location.lon}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
