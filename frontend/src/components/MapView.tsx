"use client";

import { useEffect, useMemo, useState } from "react";
import { MapContainer, TileLayer, Marker, Popup, useMap, GeoJSON } from "react-leaflet";
import L from "leaflet";

type MapCenter = {
  lat: number;
  lon: number;
  label?: string;
};

type Place = {
  name: string;
  lat: number | null;
  lon: number | null;
  address?: string;
};

const markerIcon = new L.Icon({
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});

function MapUpdater({ center, polygon }: { center?: MapCenter | null, polygon?: any }) {
  const map = useMap();
  useEffect(() => {
    if (center?.lat && center?.lon) {
      map.setView([center.lat, center.lon], 13, { animate: true });
    }
  }, [center, map]);

  useEffect(() => {
    if (polygon) {
      try {
        const layer = L.geoJSON(polygon);
        const bounds = layer.getBounds();
        if (bounds.isValid()) {
          map.fitBounds(bounds, { padding: [20, 20], animate: true });
        }
      } catch (e) {
        console.error("Error fitting bounds to polygon:", e);
      }
    }
  }, [polygon, map]);

  return null;
}

export default function MapView({
  center,
  places,
  polygon,
}: {
  center?: MapCenter | null;
  places?: Place[];
  polygon?: any;
}) {
  const [mounted, setMounted] = useState(false);
  const markers = useMemo(
    () => (places || []).filter((p) => typeof p.lat === "number" && typeof p.lon === "number"),
    [places]
  );

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return (
      <div className="map-shell">
        <div className="map map-skeleton" />
      </div>
    );
  }

  return (
    <div className="map-shell">
      <MapContainer
        center={[center?.lat || 41.0082, center?.lon || 28.9784]}
        zoom={12}
        scrollWheelZoom
        className="map"
      >
        <MapUpdater center={center} polygon={polygon} />
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {polygon && <GeoJSON key={JSON.stringify(polygon)} data={polygon} style={{ color: "#3b82f6", weight: 2, fillOpacity: 0.1 }} />}
        {markers.length > 0 ? (
          markers.map((place, idx) => (
            <Marker
              key={`${place.name}-${idx}`}
              position={[place.lat as number, place.lon as number]}
              icon={markerIcon}
            >
              <Popup>
                <strong>{place.name}</strong>
                {place.address ? <div>{place.address}</div> : null}
              </Popup>
            </Marker>
          ))
        ) : (
          <Marker position={[41.0082, 28.9784]} icon={markerIcon}>
            <Popup>İstanbul merkez</Popup>
          </Marker>
        )}
      </MapContainer>
    </div>
  );
}
