"use client";

type LocationMapProps = {
  lat: number;
  lon: number;
  className?: string;
};

/** Compact map preview centered on the user. No coordinates shown. */
export function LocationMap({ lat, lon, className = "" }: LocationMapProps) {
  const pad = 0.02;
  const bbox = [
    lon - pad,
    lat - pad * 0.75,
    lon + pad,
    lat + pad * 0.75,
  ].join("%2C");

  const embedUrl =
    `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}` +
    `&layer=mapnik&marker=${lat}%2C${lon}`;

  const openUrl = `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lon}#map=15/${lat}/${lon}`;

  return (
    <div className={`overflow-hidden rounded-xl border border-[var(--border)] ${className}`}>
      <iframe
        title="Your location on the map"
        src={embedUrl}
        className="h-44 w-full border-0 bg-slate-900"
        loading="lazy"
        referrerPolicy="no-referrer-when-downgrade"
      />
      <div className="flex items-center justify-between border-t border-[var(--border)] bg-black/20 px-3 py-2">
        <span className="text-xs text-slate-400">You are here</span>
        <a
          href={openUrl}
          target="_blank"
          rel="noreferrer"
          className="text-xs text-[var(--accent-soft)] underline"
        >
          Open full map
        </a>
      </div>
    </div>
  );
}
