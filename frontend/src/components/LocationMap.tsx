"use client";

type LocationMapProps = {
  lat: number;
  lon: number;
  className?: string;
};

function osmUrls(lat: number, lon: number, pad = 0.018) {
  const bbox = [
    lon - pad,
    lat - pad * 0.65,
    lon + pad,
    lat + pad * 0.65,
  ].join("%2C");
  const embedUrl =
    `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}` +
    `&layer=mapnik&marker=${lat}%2C${lon}`;
  const openUrl = `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lon}#map=16/${lat}/${lon}`;
  return { embedUrl, openUrl };
}

/** Map preview centered on the user. Fills its parent height. */
export function LocationMap({ lat, lon, className = "" }: LocationMapProps) {
  const { embedUrl, openUrl } = osmUrls(lat, lon);

  return (
    <div className={`flex min-h-0 flex-1 flex-col overflow-hidden ${className}`}>
      <iframe
        title="Your location on the map"
        src={embedUrl}
        className="min-h-[240px] h-[36vh] w-full flex-1 border-0 bg-slate-900 md:h-full md:min-h-[280px]"
        loading="lazy"
        referrerPolicy="no-referrer-when-downgrade"
      />
      <div className="flex items-center justify-between border-t border-[var(--border)] bg-black/30 px-3 py-2">
        <span className="text-xs text-slate-400">You are here</span>
        <a
          href={openUrl}
          target="_blank"
          rel="noreferrer"
          className="min-h-11 inline-flex items-center text-xs text-[var(--accent-soft)] underline"
        >
          Open full map
        </a>
      </div>
    </div>
  );
}

type PlaceMapThumbProps = {
  lat: number;
  lon: number;
  label: string;
  distanceKm?: number | null;
};

/** Compact map thumbnail for a directory listing row. */
export function PlaceMapThumb({ lat, lon, label, distanceKm }: PlaceMapThumbProps) {
  const { embedUrl } = osmUrls(lat, lon, 0.006);
  const mapsUrl = `https://www.google.com/maps/search/?api=1&query=${lat},${lon}`;

  return (
    <a
      href={mapsUrl}
      target="_blank"
      rel="noreferrer"
      title={`Open map for ${label}`}
      className="relative hidden h-[92px] w-[156px] shrink-0 overflow-hidden rounded-lg border border-white/10 bg-slate-900 sm:block"
    >
      <iframe
        title={`Map of ${label}`}
        src={embedUrl}
        className="pointer-events-none absolute -left-8 -top-6 h-[160px] w-[240px] border-0"
        loading="lazy"
        tabIndex={-1}
        referrerPolicy="no-referrer-when-downgrade"
      />
      <span className="pointer-events-none absolute inset-x-0 bottom-0 bg-black/60 px-1.5 py-0.5 text-[10px] text-slate-200">
        {typeof distanceKm === "number" ? `${distanceKm.toFixed(1)} km · Map` : "Map"}
      </span>
    </a>
  );
}
