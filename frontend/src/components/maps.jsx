import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useRef } from "react";
import { MapContainer, Marker, Popup, TileLayer, Tooltip, useMap, useMapEvents } from "react-leaflet";
import { Link } from "react-router-dom";
import { NotVerifiedBadge, Stars } from "./ui";

export const THAILAND_CENTER = [13.4, 100.9];
// Esri World Street Map: English labels, no API key. Note the {y}/{x} order.
const TILE = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}";
const ATTRIBUTION = 'Tiles &copy; Esri &mdash; Sources: Esri, HERE, Garmin, &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';

const pinHtml = (colour) => `
  <svg width="34" height="42" viewBox="0 0 34 42" xmlns="http://www.w3.org/2000/svg">
    <path d="M17 41s15-14.2 15-24A15 15 0 0 0 2 17c0 9.8 15 24 15 24z" fill="${colour}" stroke="#fff" stroke-width="2"/>
    <path d="M9 23l8-10 8 10z" fill="#fff"/><path d="M15.5 23l1.5-4 1.5 4z" fill="${colour}"/>
  </svg>`;
export const campIcon = L.divIcon({ html: pinHtml("#0f6647"), className: "", iconSize: [34, 42], iconAnchor: [17, 41], popupAnchor: [0, -36] });
export const meetIcon = L.divIcon({ html: pinHtml("#f58a1f"), className: "", iconSize: [34, 42], iconAnchor: [17, 41], popupAnchor: [0, -36] });
/** Grey pin: a campsite a moderator hasn't checked yet. */
export const unverifiedIcon = L.divIcon({ html: pinHtml("#8a94a6"), className: "", iconSize: [34, 42], iconAnchor: [17, 41], popupAnchor: [0, -36] });

function FitBounds({ points, maxZoom = 9 }) {
  const map = useMap();
  useEffect(() => {
    if (points.length > 1) map.fitBounds(points, { padding: [40, 40], maxZoom });
    else if (points.length === 1) map.setView(points[0], maxZoom);
  }, [map, JSON.stringify(points)]); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}

/**
 * Read-only map with several labelled pins, zoomed so all of them are visible.
 * pins = [{ position: [lat, lng], icon, title, link?: { to, text } }]
 * Labels are React text (escaped), never HTML strings. Hover shows the title;
 * a click/tap opens it, which is what works on phones.
 */
export function PinsMap({ pins, className = "h-64", maxZoom = 12 }) {
  const points = pins.map((p) => p.position);
  return (
    <MapContainer center={points[0] || THAILAND_CENTER} zoom={maxZoom} className={`rounded-xl ${className}`} scrollWheelZoom={false}>
      <TileLayer url={TILE} attribution={ATTRIBUTION} />
      <FitBounds points={points} maxZoom={maxZoom} />
      {pins.map((p) => (
        <Marker key={`${p.title}-${p.position.join(",")}`} position={p.position} icon={p.icon}>
          <Tooltip direction="top" offset={[0, -36]}>{p.title}</Tooltip>
          <Popup>
            <p className="text-sm font-semibold text-navy-900">{p.title}</p>
            {p.link && <Link to={p.link.to} className="link text-xs">{p.link.text}</Link>}
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  );
}

/** Map of campsites from the GeoJSON endpoint. */
export function CampsiteMap({ features, className = "h-full", fit = true }) {
  const points = features.map((f) => [f.geometry.coordinates[1], f.geometry.coordinates[0]]);
  return (
    <MapContainer center={THAILAND_CENTER} zoom={6} className={className} scrollWheelZoom>
      <TileLayer url={TILE} attribution={ATTRIBUTION} />
      {fit && <FitBounds points={points} />}
      {features.map((f) => (
        <Marker key={f.properties.id} position={[f.geometry.coordinates[1], f.geometry.coordinates[0]]}
                icon={f.properties.verified === false ? unverifiedIcon : campIcon}>
          <Popup>
            <div className="min-w-48">
              {f.properties.cover_image && <img src={f.properties.cover_image} alt="" className="mb-2 h-24 w-full rounded-lg object-cover" />}
              <p className="text-sm font-bold text-navy-900">{f.properties.name}</p>
              <p className="text-xs text-ink/60">{f.properties.province} · {f.properties.category}</p>
              {f.properties.verified === false && <NotVerifiedBadge className="mt-1" />}
              {f.properties.avg_rating
                ? <p className="mt-1 flex items-center gap-1 text-xs"><Stars value={f.properties.avg_rating} size={12} /> {f.properties.avg_rating.toFixed(1)}</p>
                : <p className="mt-1 text-xs text-ink/50">No reviews yet</p>}
              <Link to={`/campsites/${f.properties.id}`} className="btn-primary btn-sm mt-2 w-full !text-white">View campsite</Link>
            </div>
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  );
}

/** Small read-only map with one pin. */
export function MiniMap({ lat, lng, className = "h-56", icon = campIcon, zoom = 10 }) {
  return (
    <MapContainer center={[lat, lng]} zoom={zoom} className={`rounded-xl ${className}`} scrollWheelZoom={false}>
      <TileLayer url={TILE} attribution={ATTRIBUTION} />
      <Marker position={[lat, lng]} icon={icon} />
    </MapContainer>
  );
}

function ClickToPick({ onPick }) {
  useMapEvents({ click: (e) => onPick([Number(e.latlng.lat.toFixed(5)), Number(e.latlng.lng.toFixed(5))]) });
  return null;
}

/** Click the map to choose a point (meeting point, new campsite). */
export function PinPicker({ value, onChange, center, className = "h-56", icon = meetIcon, markers = [] }) {
  return (
    <MapContainer center={value || center || THAILAND_CENTER} zoom={value || center ? 10 : 6} className={`rounded-xl ${className}`}>
      <TileLayer url={TILE} attribution={ATTRIBUTION} />
      <ClickToPick onPick={onChange} />
      <MoveTo point={center} />
      {markers.map((m) => (
        <Marker key={m.position.join(",")} position={m.position} icon={m.icon || campIcon}>
          {m.title && <Tooltip direction="top" offset={[0, -36]}>{m.title}</Tooltip>}
        </Marker>
      ))}
      {value && <Marker position={value} icon={icon} />}
    </MapContainer>
  );
}

/** Pan to `point` when it changes after the map is shown (e.g. a different campsite is chosen). */
function MoveTo({ point }) {
  const map = useMap();
  const first = useRef(true);
  const key = point ? point.join(",") : "";
  useEffect(() => {
    if (first.current) { first.current = false; return; }
    if (point) map.setView(point, Math.max(map.getZoom(), 10));
  }, [map, key]); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}
