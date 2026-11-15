// Straight-line distance and links to real routes. The server sends the same distance on
// the trip page (core/provinces.py distance_km); this copy lets the trip form show it live.

/** Great-circle distance in km (haversine, Earth as a sphere of radius 6371 km). */
export function distanceKm([lat1, lng1], [lat2, lng2]) {
  const rad = (d) => (d * Math.PI) / 180;
  const a = Math.sin(rad(lat2 - lat1) / 2) ** 2
    + Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(rad(lng2 - lng1) / 2) ** 2;
  return 6371 * 2 * Math.asin(Math.sqrt(a));
}

/** "about 23 km", "about 4.2 km", "under 100 m". The real route is always longer. */
export function aboutKm(km) {
  if (km < 0.1) return "under 100 m";
  return `about ${km >= 10 ? Math.round(km) : km.toFixed(1)} km`;
}

/** OpenStreetMap directions (car, bicycle and foot routing all work in Thailand).
 *  The keys are OSM's engine names: "bicycle", not "bike" (an unknown name falls back to car). */
export const TRAVEL_MODES = [["car", "Car"], ["foot", "On foot"], ["bicycle", "Bike"]];

export function directionsUrl([fromLat, fromLng], [toLat, toLng], mode) {
  const route = `${fromLat},${fromLng};${toLat},${toLng}`;
  return `https://www.openstreetmap.org/directions?engine=fossgis_osrm_${mode}&route=${encodeURIComponent(route)}`;
}
