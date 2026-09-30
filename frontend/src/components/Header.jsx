export default function Header({ title, crumb, right }) {
  return (
    <div className="topbar">
      <div>
        <h2>{title}</h2>
        {crumb && <div className="crumb">{crumb}</div>}
      </div>
      {right}
    </div>
  );
}
