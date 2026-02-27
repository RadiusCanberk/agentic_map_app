"use client";

import { useEffect, useMemo, useState } from "react";
import { MapContainer, TileLayer, Marker, Popup, useMap } from "react-leaflet";
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

function MapUpdater({ center }: { center?: MapCenter | null }) {
  const map = useMap();
  useEffect(() => {
    if (center?.lat && center?.lon) {
      map.setView([center.lat, center.lon], 13, { animate: true });
    }
  }, [center, map]);
  return null;
}

export default function MapView({
  center,
  places,
}: {
  center?: MapCenter | null;
  places?: Place[];
}) {
  const [mounted, setMounted] = useState(false);
  const [mapKey, setMapKey] = useState(() => `map-${Date.now()}`);
  const markers = useMemo(
    () => (places || []).filter((p) => typeof p.lat === "number" && typeof p.lon === "number"),
    [places]
  );

  useEffect(() => {
    setMounted(true);
    setMapKey(`map-${Date.now()}`);
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
        key={mapKey}
        center={[center?.lat || 41.0082, center?.lon || 28.9784]}
        zoom={12}
        scrollWheelZoom
        className="map"
      >
        <MapUpdater center={center} />
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
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
