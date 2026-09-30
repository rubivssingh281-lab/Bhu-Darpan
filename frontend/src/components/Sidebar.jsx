import { NavLink } from "react-router-dom";
import { useAuth } from "../auth.jsx";

const LINKS = [
  { to: "/", label: "Dashboard", ic: "▦", end: true },
  { to: "/upload", label: "Upload Image", ic: "☁" },
  { to: "/analyses", label: "Analysis Results", ic: "◎" },
  { to: "/change", label: "Change Detection", ic: "⇄" },
  { to: "/reports", label: "Reports", ic: "▤" },
  { to: "/settings", label: "Settings", ic: "⚙" },
];

export default function Sidebar() {
  const { user, logout } = useAuth();
  const initials = (user?.name || "U")
    .split(" ")
    .map((s) => s[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="logo">🛰️</div>
        <div>
          <h1>Bhū-Darpan</h1>
          <span>Satellite AI</span>
        </div>
      </div>

      <nav className="nav">
        {LINKS.map((l) => (
          <NavLink key={l.to} to={l.to} end={l.end}>
            <span className="ic">{l.ic}</span>
            {l.label}
          </NavLink>
        ))}
      </nav>

      <div className="side-foot">
        <div className="side-user">
          <div className="av">{initials}</div>
          <div>
            <div className="nm">{user?.name}</div>
            <div className="em">{user?.email}</div>
          </div>
        </div>
        <button className="btn-logout" onClick={logout}>
          Sign out
        </button>
      </div>
    </aside>
  );
}
