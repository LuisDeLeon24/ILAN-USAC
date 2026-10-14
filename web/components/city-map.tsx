export function CityMap() {
  return (
    <svg className="city-map" viewBox="0 0 1200 800" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
      <g className="city-map-lines">
        <path d="M0 110H1200 M0 250H1200 M0 430H1200 M0 610H1200 M0 740H1200" />
        <path d="M90 0V800 M250 0V800 M460 0V800 M700 0V800 M940 0V800 M1100 0V800" />
        <path d="M90 180H460 M250 110V430 M460 340H940 M700 250V610 M940 430V740" />
        <rect x="250" y="110" width="210" height="140" />
        <rect x="700" y="250" width="240" height="180" />
        <rect x="90" y="430" width="160" height="180" />
      </g>
      <g className="city-map-points">
        <circle cx="250" cy="250" r="4" />
        <circle cx="700" cy="110" r="3" />
        <circle cx="940" cy="430" r="4" />
        <circle cx="460" cy="610" r="3" />
        <circle cx="1100" cy="180" r="3" />
      </g>
    </svg>
  );
}
