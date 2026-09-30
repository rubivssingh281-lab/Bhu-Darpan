import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import L from "leaflet";

// Custom divIcon avoids the broken default-marker-image issue with bundlers.
const pin = L.divIcon({
  className: "",
  html: `<div style="width:16px;height:16px;border-radius:50% 50% 50% 0;
    background:#1565C0;transform:rotate(-45deg);border:2px solid #fff;
    box-shadow:0 2px 6px rgba(0,0,0,.4)"></div>`,
  iconSize: [16, 16],
  iconAnchor: [8, 16],
});

export default function MapView({ points = [] }) {
  const located = points.filter((p) => p.location && p.location.lat != null);
  const center = located.length
    ? [located[0].location.lat, located[0].location.lon]
    : [22.9734, 78.6569]; // India centroid fallback

  return (
    <div className="map-box">
      <MapContainer center={center} zoom={located.length ? 6 : 4} style={{ height: "100%", width: "100%" }} scrollWheelZoom={false}>
        <TileLayer
          attribution='&copy; OpenStreetMap contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {located.map((p) => (
          <Marker key={p.id} position={[p.location.lat, p.location.lon]} icon={pin}>
            <Popup>
              <b>{p.name}</b>
              <br />
              Confidence: {p.confidence}%
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}
