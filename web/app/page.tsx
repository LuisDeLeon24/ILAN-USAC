"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { CityMap } from "@/components/city-map";
import { Frame } from "@/components/frame";
import { HeroAnimation } from "@/components/hero-animation";
import { Button } from "@/components/ui/button";
import { team, type TeamMember } from "@/content/team";

const DASHBOARD_HREF = "/sitios";

const SECTIONS = [
  { id: "inicio", label: "Inicio" },
  { id: "problema", label: "El problema" },
  { id: "solucion", label: "La solución" },
  { id: "como-funciona", label: "Cómo funciona" },
  { id: "privacidad", label: "Privacidad" },
  { id: "para-quien", label: "Para quién" },
  { id: "modelo", label: "Modelo de negocio" },
  { id: "impacto", label: "Impacto" },
  { id: "equipo", label: "El equipo" },
  { id: "cierre", label: "Visión y cierre" },
] as const;

const PROBLEM_POINTS = [
  "El monitoreo humano se cansa y se distrae.",
  "Los incidentes se descubren después, revisando grabaciones.",
  "Reemplazar toda la infraestructura es caro y lento.",
];

const SOLUTION_CARDS = [
  {
    title: "Usa lo que ya tienes",
    text: "Se conecta a cámaras y sensores instalados, sin sustituirlos.",
  },
  {
    title: "Detecta en tiempo real",
    text: "Intrusiones, horarios no permitidos, merodeo y aforo.",
  },
  {
    title: "Avisa al instante",
    text: "Alertas con foto al encargado de monitoreo.",
  },
];

const STEPS = ["Cámaras y sensores", "IA en el sitio", "Evento detectado", "Alerta y dashboard"];

const AUDIENCE = ["Empresas", "Industrias", "Instituciones educativas", "Centros logísticos"];

const BUSINESS = [
  {
    title: "Implementación",
    text: "Cobro único por configurar cámaras y sensores.",
  },
  {
    title: "Pago por tiempo analizado",
    text: "Pagas solo por los minutos que la IA vigila.",
  },
];

const PILLARS = [
  "Infraestructura tecnológica en comunidades y ciudad.",
  "Mejor calidad de vida a través de espacios seguros.",
  "Oportunidades de talento en tecnología.",
];

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

function EnterLink({ href }: { href: string }) {
  return (
    <Button asChild variant="primary">
      <Link href={href}>Ingresar al centro de monitoreo</Link>
    </Button>
  );
}

function MemberPhoto({ member }: { member: TeamMember }) {
  const src = member.photo ? photoSrc(member.photo) : "";
  const [failed, setFailed] = useState(!src);
  if (!failed && src) {
    return <img className="team-photo" src={src} alt="" onError={() => setFailed(true)} />;
  }
  return (
    <span className="team-photo" aria-hidden="true">
      {initials(member.name)}
    </span>
  );
}

function MemberName({ member }: { member: TeamMember }) {
  const href = profileHref(member.linkedin);
  if (!href) {
    return <p className="pitch-name">{member.name}</p>;
  }
  return (
    <p className="pitch-name">
      <a href={href} target="_blank" rel="noopener noreferrer">
        {member.name}
      </a>
    </p>
  );
}

export default function LandingPage() {
  const scroller = useRef<HTMLDivElement>(null);
  const indexRef = useRef(0);
  const keyScroll = useRef(false);
  const keyTimer = useRef(0);
  const [index, setIndex] = useState(0);
  const [entered, setEntered] = useState(false);
  const enterHref = entered ? DASHBOARD_HREF : "/login";

  useEffect(() => {
    setEntered(Boolean(sessionStorage.getItem("sentinel_token")));
  }, []);

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
    const top = root.scrollTop + slide.getBoundingClientRect().top - root.getBoundingClientRect().top;
    root.scrollTo({ top, behavior: scrollBehavior() });
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
      const rootTop = root.getBoundingClientRect().top;
      let best = 0;
      let bestDistance = Number.POSITIVE_INFINITY;
      slides.forEach((slide, slideIndex) => {
        const distance = Math.abs(slide.getBoundingClientRect().top - rootTop);
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
    root.addEventListener("scroll", onScroll, { passive: true });
    root.addEventListener("scrollend", onScrollEnd);
    return () => {
      cancelAnimationFrame(frame);
      root.removeEventListener("scroll", onScroll);
      root.removeEventListener("scrollend", onScrollEnd);
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
        if (tag === "INPUT" || tag === "TEXTAREA" || target.isContentEditable) {
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
    <div className="pitch" ref={scroller}>
      <img className="pitch-brand" src="/brand/sentinel-wordmark-white.png" alt="Sentinel" />
      <nav className="pitch-dots" aria-label="Secciones">
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

      <section className="pitch-slide pitch-hero" id="inicio" data-slide="0" aria-label="Inicio">
        <div className="pitch-inner pitch-hero-inner">
          <div className="pitch-hero-copy">
            <h1 className="pitch-title">Tus cámaras ya ven. Ahora también entienden.</h1>
            <p className="pitch-lead">
              SentinelAI convierte las cámaras y sensores que ya tienes en un sistema que detecta riesgos y
              avisa en segundos.
            </p>
            <EnterLink href={enterHref} />
          </div>
          <HeroAnimation />
        </div>
      </section>

      <section className="pitch-slide" id="problema" data-slide="1" aria-label="El problema">
        <CityMap />
        <div className="pitch-inner">
          <h2 className="pitch-title">Las cámaras graban, pero nadie las mira todo el tiempo.</h2>
          <Frame className="pitch-panel">
            <ul className="pitch-points">
              {PROBLEM_POINTS.map((point) => (
                <li key={point}>{point}</li>
              ))}
            </ul>
          </Frame>
        </div>
      </section>

      <section className="pitch-slide" id="solucion" data-slide="2" aria-label="La solución">
        <CityMap />
        <div className="pitch-inner">
          <h2 className="pitch-title">Inteligencia sobre la infraestructura que ya existe.</h2>
          <ul className="pitch-grid pitch-grid-3">
            {SOLUTION_CARDS.map((card) => (
              <li key={card.title}>
                <Frame>
                  <h3 className="pitch-card-title">{card.title}</h3>
                  <p className="pitch-card-copy">{card.text}</p>
                </Frame>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="pitch-slide" id="como-funciona" data-slide="3" aria-label="Cómo funciona">
        <CityMap />
        <div className="pitch-inner">
          <h2 className="pitch-title">Cómo funciona</h2>
          <ol className="pitch-grid pitch-grid-4 pitch-flow">
            {STEPS.map((step) => (
              <li key={step}>
                <Frame>
                  <p className="pitch-step">{step}</p>
                </Frame>
              </li>
            ))}
          </ol>
          <Frame className="pitch-panel">
            <p className="pitch-card-copy">
              Senti responde preguntas sobre lo ocurrido, en español.
            </p>
          </Frame>
        </div>
      </section>

      <section className="pitch-slide" id="privacidad" data-slide="4" aria-label="Privacidad">
        <CityMap />
        <div className="pitch-inner">
          <h2 className="pitch-title">El video nunca sale de tus instalaciones.</h2>
          <Frame className="pitch-panel">
            <p className="pitch-card-copy">
              El análisis ocurre en un equipo local. A la nube solo viaja lo importante: el evento, su foto
              y el tiempo analizado.
            </p>
          </Frame>
        </div>
      </section>

      <section className="pitch-slide" id="para-quien" data-slide="5" aria-label="Para quién">
        <CityMap />
        <div className="pitch-inner">
          <h2 className="pitch-title">Hecho para espacios con alta actividad.</h2>
          <ul className="pitch-grid pitch-grid-4">
            {AUDIENCE.map((item) => (
              <li key={item}>
                <Frame>
                  <p className="pitch-card-title">{item}</p>
                </Frame>
              </li>
            ))}
          </ul>
          <Frame className="pitch-panel">
            <p className="pitch-card-copy">Comenzamos en Guatemala, con visión hacia Latinoamérica.</p>
          </Frame>
        </div>
      </section>

      <section className="pitch-slide" id="modelo" data-slide="6" aria-label="Modelo de negocio">
        <CityMap />
        <div className="pitch-inner">
          <h2 className="pitch-title">Implementación progresiva. Pago por uso.</h2>
          <ul className="pitch-grid pitch-grid-2">
            {BUSINESS.map((block) => (
              <li key={block.title}>
                <Frame>
                  <h3 className="pitch-card-title">{block.title}</h3>
                  <p className="pitch-card-copy">{block.text}</p>
                </Frame>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="pitch-slide" id="impacto" data-slide="7" aria-label="Impacto">
        <CityMap />
        <div className="pitch-inner">
          <h2 className="pitch-title">Seguridad que construye comunidad.</h2>
          <ul className="pitch-grid pitch-grid-3">
            {PILLARS.map((pillar) => (
              <li key={pillar}>
                <Frame>
                  <p className="pitch-card-copy">{pillar}</p>
                </Frame>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="pitch-slide" id="equipo" data-slide="8" aria-label="El equipo">
        <CityMap />
        <div className="pitch-inner">
          <h2 className="pitch-title">El equipo</h2>
          <ul className="pitch-grid pitch-grid-4">
            {team.map((member, memberIndex) => (
              <li key={`${member.name}-${memberIndex}`}>
                <Frame>
                  <div className="team-card">
                    <MemberPhoto member={member} />
                    <MemberName member={member} />
                    <p className="pitch-role">{member.role}</p>
                  </div>
                </Frame>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="pitch-slide" id="cierre" data-slide="9" aria-label="Visión y cierre">
        <CityMap />
        <div className="pitch-inner">
          <h2 className="pitch-title">De detectar eventos a anticiparlos.</h2>
          <Frame className="pitch-panel">
            <p className="pitch-card-copy">
              Hoy detectamos y alertamos. Mañana: análisis predictivo de riesgos y respuestas automatizadas.
            </p>
          </Frame>
          <EnterLink href={enterHref} />
        </div>
      </section>
    </div>
  );
}
