"use client";

import { ReactNode, useEffect, useRef, useState } from "react";

import { team, type TeamMember } from "@/content/team";

const SECTIONS = [
  { id: "portada", label: "Portada" },
  { id: "introduccion", label: "Introducción" },
  { id: "mision", label: "Misión" },
  { id: "credibilidad", label: "Credibilidad" },
  { id: "validacion", label: "Validación" },
  { id: "casos", label: "Casos de uso" },
  { id: "demanda", label: "Demanda" },
  { id: "mercado", label: "Números" },
  { id: "momentum", label: "Trayectoria" },
  { id: "equipo", label: "El equipo" },
  { id: "capital", label: "Capital" },
  { id: "demo", label: "Demo" },
  { id: "video", label: "Video" },
  { id: "gracias", label: "Pruebalo ahora" },
] as const;

const VIDEO_SLIDE = SECTIONS.findIndex((section) => section.id === "video");

const INTRO_POINTS = ["Seguridad industrial", "Respuesta inmediata", "IA como pilar central"];

const MISSION_VALUES = ["Detección", "Respuesta", "Evidencia"];

const PROOF_FIELD = [
  "Nace en Guatemala, dentro de ILAN.",
  "122 pruebas automáticas en la API y el worker.",
  "Alertas con foto por Telegram y WhatsApp.",
  "Reglas por zona y horario, con evidencia.",
];

const PROOF_STACK = [
  "YOLO, OpenCV y ByteTrack en un equipo local.",
  "El video se analiza en el sitio y no sale de planta.",
  "Se conecta a cámaras RTSP y sensores que ya existen.",
  "Si cae internet, el worker guarda y reenvía.",
];

const FIELD_CARDS = [
  {
    source: "17 monitores · Ciudad de Guatemala",
    title: "14 de 17 sin vínculo con una institución de seguridad",
  },
  {
    source: "17 monitores · Ciudad de Guatemala",
    title: "13 de 17: más pantallas no agilizan el monitoreo",
  },
  {
    source: "Banca, industria, municipio y comercio",
    title: "Bac, Vivibanco, Energuate, municipalidades y Maxi Despensa",
  },
  {
    source: "Sergio · operador en Vivibanco",
    title: "No puede vigilar varias cámaras durante una jornada de 8 horas",
    detail: "En logística vio invasión de áreas y personal no autorizado.",
  },
] as const;

const CASE_ROWS = [
  {
    lead: "Se conecta a lo que ya existe",
    points: ["Cámaras IP por RTSP", "Puerta, movimiento, humo y pánico"],
  },
  {
    lead: "Espacios con alta actividad",
    points: ["Empresas", "Industrias", "Instituciones educativas", "Centros logísticos"],
  },
  {
    lead: "Detecta",
    points: [
      "Intrusión en zona restringida",
      "Presencia fuera de horario",
      "Merodeo",
      "Aforo",
    ],
  },
] as const;

const MOMENTUM = [
  { place: "INTECAP Escuintla", line: "Invitados" },
  { place: "UVG CREA", line: "Presentado" },
  { place: "ILAN USAC", line: "Finalista" },
] as const;

const DEMAND = [
  "6 de 17 no generan un reporte al final del día.",
  "Q1,532 al mes: menos del 74% de contratar otro monitor.",
  "Licencia mensual por implementar y mantener la solución.",
] as const;

const MARKET = [
  {
    key: "TAM",
    label: "Empresas con 20 o más empleados",
    count: "10,977",
    money: "Q202 M al año",
  },
  {
    key: "SAM",
    label: "Guatemala y sectores objetivo",
    count: "3,408",
    money: "Q63 M al año",
  },
  {
    key: "SOM",
    label: "Clientes al cierre del año 3",
    count: "91",
    money: "Q1.7 M al año",
  },
] as const;

const NEXT_KEYS = new Set(["ArrowDown", "ArrowRight", "PageDown", " "]);
const PREV_KEYS = new Set(["ArrowUp", "ArrowLeft", "PageUp"]);

function initials(name: string) {
  const words = name.trim().split(/\s+/).filter(Boolean);
  const marks = words
    .map((word) => Array.from(word).find((char) => /\p{L}/u.test(char)) ?? "")
    .filter(Boolean);
  if (marks.length === 0) {
    return "?";
  }
  const chosen = marks.length === 1 ? marks[0] : `${marks[0]}${marks[marks.length - 1]}`;
  return chosen.toLocaleUpperCase("es");
}

function photoSrc(photo: string) {
  const file = photo.trim().split(/[/\\]/).filter(Boolean).pop();
  return file ? `/team/${file}` : "";
}

function profileHref(value: string | undefined) {
  if (!value?.trim()) {
    return "";
  }
  try {
    const url = new URL(value.trim());
    return url.protocol === "https:" || url.protocol === "http:" ? url.toString() : "";
  } catch {
    return "";
  }
}

function scrollBehavior(): ScrollBehavior {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
}

function IconMark() {
  return <img className="deck-logo" src="/brand/sentinel-icon.png" alt="" />;
}

function SlideTitle({ children }: { children: ReactNode }) {
  return <h2 className="deck-slide-title">{children}</h2>;
}

function DemoVideo({ active }: { active: boolean }) {
  const video = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const node = video.current;
    if (!node) {
      return;
    }
    if (!active) {
      node.pause();
      return;
    }
    void node.play().catch(() => undefined);
  }, [active]);

  return (
    <video
      ref={video}
      className="deck-video"
      src="/demo.mp4"
      controls
      playsInline
      preload="metadata"
    >
      Tu navegador no puede reproducir este video.
    </video>
  );
}

function MemberDisc({ member }: { member: TeamMember }) {
  const src = member.photo ? photoSrc(member.photo) : "";
  const [failed, setFailed] = useState(!src);
  if (!failed && src) {
    return (
      <div className="deck-disc deck-disc-photo">
        <img src={src} alt="" onError={() => setFailed(true)} />
      </div>
    );
  }
  return (
    <div className="deck-disc" aria-hidden="true">
      <span className="deck-initials">{initials(member.name)}</span>
    </div>
  );
}

function MemberName({ member }: { member: TeamMember }) {
  const href = profileHref(member.linkedin);
  if (!href) {
    return <p className="deck-line">{member.name}</p>;
  }
  return (
    <p className="deck-line">
      <a href={href} target="_blank" rel="noopener noreferrer">
        {member.name}
      </a>
    </p>
  );
}

function Split({
  mark,
  children,
}: {
  mark: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="deck-split">
      <div className="deck-mark">{mark}</div>
      <div className="deck-copy">{children}</div>
    </div>
  );
}

export default function DeckPage() {
  const scroller = useRef<HTMLDivElement>(null);
  const indexRef = useRef(0);
  const keyScroll = useRef(false);
  const keyTimer = useRef(0);
  const [index, setIndex] = useState(0);

  function scrollToIndex(next: number) {
    const root = scroller.current;
    if (!root) {
      return;
    }
    const slides = [...root.querySelectorAll<HTMLElement>("[data-slide]")];
    const clamped = Math.max(0, Math.min(slides.length - 1, next));
    const slide = slides[clamped];
    if (!slide || clamped === indexRef.current) {
      return;
    }
    indexRef.current = clamped;
    setIndex(clamped);
    keyScroll.current = true;
    window.clearTimeout(keyTimer.current);
    keyTimer.current = window.setTimeout(() => {
      keyScroll.current = false;
    }, 900);
    const left = root.scrollLeft + slide.getBoundingClientRect().left - root.getBoundingClientRect().left;
    root.scrollTo({ left, behavior: scrollBehavior() });
  }

  useEffect(() => {
    const root = scroller.current;
    if (!root) {
      return;
    }
    let frame = 0;
    const sync = () => {
      if (keyScroll.current) {
        return;
      }
      const slides = [...root.querySelectorAll<HTMLElement>("[data-slide]")];
      const rootLeft = root.getBoundingClientRect().left;
      let best = 0;
      let bestDistance = Number.POSITIVE_INFINITY;
      slides.forEach((slide, slideIndex) => {
        const distance = Math.abs(slide.getBoundingClientRect().left - rootLeft);
        if (distance < bestDistance) {
          bestDistance = distance;
          best = slideIndex;
        }
      });
      if (best !== indexRef.current) {
        indexRef.current = best;
        setIndex(best);
      }
    };
    const onScroll = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(sync);
    };
    const onScrollEnd = () => {
      keyScroll.current = false;
      sync();
    };
    const onWheel = (event: WheelEvent) => {
      if (Math.abs(event.deltaY) <= Math.abs(event.deltaX)) {
        return;
      }
      event.preventDefault();
      if (keyScroll.current) {
        return;
      }
      if (event.deltaY > 0) {
        scrollToIndex(indexRef.current + 1);
      } else {
        scrollToIndex(indexRef.current - 1);
      }
    };
    root.addEventListener("scroll", onScroll, { passive: true });
    root.addEventListener("scrollend", onScrollEnd);
    root.addEventListener("wheel", onWheel, { passive: false });
    return () => {
      cancelAnimationFrame(frame);
      root.removeEventListener("scroll", onScroll);
      root.removeEventListener("scrollend", onScrollEnd);
      root.removeEventListener("wheel", onWheel);
    };
  }, []);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.repeat || event.altKey || event.ctrlKey || event.metaKey) {
        return;
      }
      const target = event.target;
      if (target instanceof HTMLElement) {
        const tag = target.tagName;
        if (tag === "INPUT" || tag === "TEXTAREA" || tag === "VIDEO" || target.isContentEditable) {
          return;
        }
      }
      if (NEXT_KEYS.has(event.key)) {
        event.preventDefault();
        scrollToIndex(indexRef.current + 1);
      } else if (PREV_KEYS.has(event.key)) {
        event.preventDefault();
        scrollToIndex(indexRef.current - 1);
      }
    }
    window.addEventListener("keydown", onKey, { capture: true });
    return () => window.removeEventListener("keydown", onKey, { capture: true });
  }, []);

  return (
    <div className="deck" ref={scroller}>
      {/*
        THESIS: A night-ops title card. The deck is a sequence of split plates, not a card grid.
        OWN-WORLD: Navy field, cream disc, cyan hairline, official mark, Poppins 500–800.
        STORY: The visitor reads Sentinel as infrastructure, then the offer, then enters.
        FIRST VIEWPORT: Horizontal navy plates. 50/50 split, official mark left, wordmark + line + role right. Plain field, no plat.
        FORM: Title-card split from the supplied layout reference. Precisely specified; no seed.
        FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, and DESIGN.md
      */}
      <nav className="deck-dots" aria-label="Secciones">
        {SECTIONS.map((section, sectionIndex) => (
          <button
            key={section.id}
            type="button"
            className="pitch-dot"
            aria-label={section.label}
            aria-current={sectionIndex === index ? "true" : undefined}
            onClick={() => scrollToIndex(sectionIndex)}
          />
        ))}
      </nav>

      <section className="deck-slide" id="portada" data-slide="0" aria-label="Portada">
        <Split mark={<IconMark />}>
          <h1 className="deck-title">
            <img className="deck-wordmark" src="/brand/sentinel-wordmark-white.png" alt="Sentinel" />
          </h1>
          <p className="deck-line deck-support">Detección de riesgos con inteligencia artificial</p>
          <p className="deck-role deck-org">ILAN USAC</p>
        </Split>
      </section>

      <section className="deck-slide deck-slide-intro" id="introduccion" data-slide="1" aria-label="Introducción">
        <SlideTitle>Introducción</SlideTitle>
        <Split mark={<IconMark />}>
          <h2 className="deck-title">
            <img className="deck-wordmark" src="/brand/sentinel-wordmark-white.png" alt="Sentinel" />
          </h2>
          <ul className="deck-points">
            {INTRO_POINTS.map((point) => (
              <li key={point}>{point}</li>
            ))}
          </ul>
        </Split>
      </section>

      <section className="deck-slide" id="mision" data-slide="2" aria-label="Misión">
        <SlideTitle>Misión</SlideTitle>
        <div className="deck-mission">
          <p className="deck-mission-lead">Construir:</p>
          <ol className="deck-mission-list">
            {MISSION_VALUES.map((value, valueIndex) => (
              <li key={value}>
                <span className="deck-mission-num" aria-hidden="true">
                  {valueIndex + 1}
                </span>
                <span className="deck-mission-word">{value}</span>
              </li>
            ))}
          </ol>
          <p className="deck-mission-close">con inteligencia artificial</p>
        </div>
      </section>

      <section className="deck-slide" id="credibilidad" data-slide="3" aria-label="Credibilidad">
        <SlideTitle>Credibilidad</SlideTitle>
        <div className="deck-proof">
          <div className="deck-proof-grid">
            <div>
              <h3 className="deck-proof-kicker">Campo y producto</h3>
              <ul className="deck-points deck-proof-points">
                {PROOF_FIELD.map((point) => (
                  <li key={point}>{point}</li>
                ))}
              </ul>
            </div>
            <div>
              <h3 className="deck-proof-kicker">La pila técnica</h3>
              <ul className="deck-points deck-proof-points">
                {PROOF_STACK.map((point) => (
                  <li key={point}>{point}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </section>

      <section className="deck-slide" id="validacion" data-slide="4" aria-label="Validación">
        <SlideTitle>Validación</SlideTitle>
        <div className="deck-field">
          <ul className="deck-field-grid">
            {FIELD_CARDS.map((card) => (
              <li className="deck-field-card" key={card.title}>
                <p className="deck-field-source">{card.source}</p>
                <p className="deck-field-card-title">{card.title}</p>
                {"detail" in card ? <p className="deck-field-detail">{card.detail}</p> : null}
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="deck-slide" id="casos" data-slide="5" aria-label="Casos de uso">
        <SlideTitle>Casos de uso</SlideTitle>
        <div className="deck-cases">
          <div className="deck-cases-panel">
            <p className="deck-cases-kicker">En el sitio</p>
            <ul className="deck-cases-rows">
              {CASE_ROWS.map((row) => (
                <li key={row.lead}>
                  <p className="deck-cases-lead">{row.lead}</p>
                  <ul className="deck-points deck-proof-points">
                    {row.points.map((point) => (
                      <li key={point}>{point}</li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      <section className="deck-slide" id="demanda" data-slide="6" aria-label="Demanda">
        <SlideTitle>Demanda</SlideTitle>
        <div className="deck-demand">
          <ul className="deck-demand-list">
            {DEMAND.map((point) => (
              <li key={point}>{point}</li>
            ))}
          </ul>
        </div>
      </section>

      <section className="deck-slide" id="mercado" data-slide="7" aria-label="Números">
        <SlideTitle>Números</SlideTitle>
        <div className="deck-tam">
          <p className="deck-cases-kicker">Guatemala · empresas formales</p>
          <ol className="deck-tam-list">
            {MARKET.map((band) => (
              <li key={band.key}>
                <p className="deck-tam-key">{band.key}</p>
                <p className="deck-tam-count">{band.count}</p>
                <p className="deck-tam-label">{band.label}</p>
                <p className="deck-tam-money">{band.money}</p>
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="deck-slide" id="momentum" data-slide="8" aria-label="Trayectoria">
        <SlideTitle>Trayectoria</SlideTitle>
        <div className="deck-momentum">
          <div className="deck-momentum-panel">
            <p className="deck-cases-kicker">Reconocimiento</p>
            <ol className="deck-momentum-chart">
              {MOMENTUM.map((step) => (
                <li key={step.place}>
                  <span className="deck-momentum-mark" aria-hidden="true" />
                  <p className="deck-momentum-line">{step.line}</p>
                  <p className="deck-momentum-place">{step.place}</p>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </section>

      <section className="deck-slide" id="equipo" data-slide="9" aria-label="El equipo">
        <SlideTitle>Equipo</SlideTitle>
        <div className="deck-team">
          <ul className="deck-team-grid">
            {team.map((member) => (
              <li className="deck-person" key={member.name}>
                <MemberDisc member={member} />
                <MemberName member={member} />
                <ul className="deck-person-bg">
                  {(member.background ?? [member.role]).map((line) => (
                    <li key={line}>{line}</li>
                  ))}
                </ul>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="deck-slide" id="capital" data-slide="10" aria-label="Capital">
        <SlideTitle>Capital</SlideTitle>
        <div className="deck-seed">
          <p className="deck-seed-line">Buscamos</p>
          <p className="deck-seed-amount">US$8,000</p>
          <p className="deck-seed-line">de capital semilla</p>
        </div>
      </section>

      <section className="deck-slide" id="demo" data-slide="11" aria-label="Demo">
        <p className="deck-center-word">Demo</p>
      </section>

      <section className="deck-slide" id="video" data-slide="12" aria-label="Video de la demo">
        <DemoVideo active={index === VIDEO_SLIDE} />
      </section>

      <section className="deck-slide" id="gracias" data-slide="13" aria-label="Pruebalo ahora">
        <div className="deck-thanks">
          <p className="deck-cta">Pruebalo ahora</p>
          <img
            className="deck-qr"
            src="/brand/ilan-usac-qr.png"
            alt="Código QR para probar Sentinel"
          />
        </div>
      </section>
    </div>
  );
}
