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

const STORAGE_KEY = "resq_last_coords";

function readStoredCoords(): UserCoords | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<UserCoords>;
    if (typeof parsed.lat === "number" && typeof parsed.lon === "number") {
      return {
        lat: parsed.lat,
        lon: parsed.lon,
        accuracy: typeof parsed.accuracy === "number" ? parsed.accuracy : null,
      };
    }
  } catch {
    return null;
  }
  return null;
}

function writeStoredCoords(coords: UserCoords) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(coords));
  } catch {
    /* ignore quota / private mode */
  }
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
        const next = {
          lat: pos.coords.latitude,
          lon: pos.coords.longitude,
          accuracy: pos.coords.accuracy ?? null,
        };
        writeStoredCoords(next);
        setCoords(next);
        setStatus("granted");
      },
      (err) => {
        const stored = readStoredCoords();
        if (stored) {
          setCoords(stored);
          setStatus("granted");
          setError(null);
          return;
        }
        setCoords(null);
        if (err.code === err.PERMISSION_DENIED) {
          setStatus("denied");
          setError("Location access was denied. Turn it on to find hospitals near you.");
        } else {
          setStatus("error");
          setError("Could not find your location. Please try again.");
        }
      },
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 60_000 },
    );
  }, []);

  useEffect(() => {
    const stored = readStoredCoords();
    if (stored) {
      setCoords(stored);
      setStatus("granted");
    }
    if (requestOnMount) refresh();
  }, [requestOnMount, refresh]);

  return { coords, status, error, refresh };
}
