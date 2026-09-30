import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import api, { mediaUrl } from "../api.js";
import Header from "../components/Header.jsx";
import AnalysisResult from "../components/AnalysisResult.jsx";

export default function AnalysisDetail() {
  const { id } = useParams();
  const nav = useNavigate();
  const [a, setA] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api.get(`/api/analysis/${id}`)
      .then((r) => setA(r.data))
      .catch(() => setErr("Analysis not found."));
  }, [id]);

  async function remove() {
    if (!confirm("Delete this analysis?")) return;
    await api.delete(`/api/analysis/${id}`);
    nav("/analyses");
  }

  if (err) return <><Header title="Analysis" /><div className="content"><div className="card empty">{err}</div></div></>;
  if (!a) return <><Header title="Analysis" /><div className="center-load"><span className="loader" /></div></>;

  return (
    <>
      <Header
        title={a.name}
        crumb={`Analysed ${a.created_at}`}
        right={
          <div className="wrap-actions">
            {a.report_url && <a className="btn ghost sm" href={mediaUrl(a.report_url)} target="_blank" rel="noreferrer">▤ PDF</a>}
            <Link to="/analyses" className="btn ghost sm">← Back</Link>
            <button className="btn danger sm" onClick={remove}>Delete</button>
          </div>
        }
      />
      <div className="content">
        <AnalysisResult a={a} />
      </div>
    </>
  );
}
