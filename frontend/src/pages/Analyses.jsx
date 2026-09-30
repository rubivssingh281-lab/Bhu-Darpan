import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { mediaUrl } from "../api.js";
import Header from "../components/Header.jsx";

export default function Analyses() {
  const [items, setItems] = useState(null);

  useEffect(() => {
    api.get("/api/analysis").then((r) => setItems(r.data));
  }, []);

  return (
    <>
      <Header
        title="Analysis Results"
        crumb="All satellite scenes you have analysed"
        right={<Link to="/upload" className="btn sm">☁ New analysis</Link>}
      />
      <div className="content">
        {!items ? (
          <div className="center-load"><span className="loader" /></div>
        ) : items.length === 0 ? (
          <div className="card empty">
            <div className="em-ic">◎</div>
            <h3>No analyses yet</h3>
            <p style={{ margin: "8px 0 18px" }}>Upload a satellite image to get started.</p>
            <Link to="/upload" className="btn">Upload an image</Link>
          </div>
        ) : (
          <div className="thumb-grid">
            {items.map((a) => {
              const dom = Object.entries(a.land_cover).sort((x, y) => y[1] - x[1])[0];
              return (
                <Link to={`/analyses/${a.id}`} key={a.id} className="card a-card">
                  <div className="a-thumb"><img src={mediaUrl(a.segmentation_url)} alt={a.name} /></div>
                  <div className="flex between center">
                    <b style={{ fontSize: 14 }}>{a.name}</b>
                    <span className="chip">{a.confidence}%</span>
                  </div>
                  <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 4 }}>
                    {a.created_at?.slice(0, 16)}
                  </div>
                  <div style={{ fontSize: 12.5, marginTop: 8 }}>
                    Dominant: <b>{dom?.[0]}</b> ({dom?.[1].toFixed(1)}%) · {a.objects?.length || 0} objects
                  </div>
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </>
  );
}
