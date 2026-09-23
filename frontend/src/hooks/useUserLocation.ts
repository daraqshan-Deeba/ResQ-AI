"use client";

import { useCallback, useEffect, useState } from "react";

export type LocationStatus =
  | "idle"
  | "loading"
  | "granted"
  | "denied"
  | "unsupported"
  | "error";

export interface UserCoords {
  lat: number;
  lon: number;
  accuracy: number | null;
}

export function useUserLocation(requestOnMount = true) {
  const [coords, setCoords] = useState<UserCoords | null>(null);
  const [status, setStatus] = useState<LocationStatus>("idle");
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(() => {
    if (!navigator.geolocation) {
      setStatus("unsupported");
      setError("Location is not available in this browser.");
      return;
    }

    setStatus("loading");
    setError(null);

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setCoords({
          lat: pos.coords.latitude,
          lon: pos.coords.longitude,
          accuracy: pos.coords.accuracy ?? null,
        });
        setStatus("granted");
      },
      (err) => {
        setCoords(null);
        if (err.code === err.PERMISSION_DENIED) {
          setStatus("denied");
          setError("Location access was denied. Turn it on to see weather and traffic near you.");
        } else {
          setStatus("error");
          setError("Could not find your location. Please try again.");
        }
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 60_000 },
    );
  }, []);

  useEffect(() => {
    if (requestOnMount) refresh();
  }, [requestOnMount, refresh]);

  return { coords, status, error, refresh };
}
