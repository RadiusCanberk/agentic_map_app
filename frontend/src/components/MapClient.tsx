"use client";

import dynamic from "next/dynamic";

const MapView = dynamic(() => import("@/components/MapView"), { ssr: false });

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

export default function MapClient({
  center,
  places,
  polygon,
}: {
  center?: MapCenter | null;
  places?: Place[];
  polygon?: any;
}) {
  return <MapView center={center} places={places} polygon={polygon} />;
}
