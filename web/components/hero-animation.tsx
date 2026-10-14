"use client";

import { useEffect, useRef } from "react";

function Walker({ className }: { className: string }) {
  return (
    <g className={className}>
      <g className="hero-bob">
        <rect className="hero-box hero-detect" x="-36" y="-122" width="72" height="128" />
        <text className="hero-label hero-detect" x="-34" y="-128">
          Persona
        </text>
        <circle className="hero-person" cx="0" cy="-98" r="13" />
        <path className="hero-person" d="M0 -85 V-42" />
        <path className="hero-person hero-arm hero-arm-a" d="M0 -72 L-20 -48" />
        <path className="hero-person hero-arm hero-arm-b" d="M0 -72 L20 -48" />
        <g transform="translate(0 -42)">
          <path className="hero-person hero-leg hero-leg-a" d="M0 0 L-16 40" />
          <path className="hero-person hero-leg hero-leg-b" d="M0 0 L16 40" />
        </g>
      </g>
    </g>
  );
}

export function HeroAnimation() {
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const root = rootRef.current;
    if (!root) {
      return;
    }
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
    const applyReduce = () => {
      root.classList.toggle("hero-static", reduce.matches);
    };
    applyReduce();
    reduce.addEventListener("change", applyReduce);

    const scroller = root.closest(".pitch");
    let onScreen = true;
    const observer = new IntersectionObserver(
      ([entry]) => {
        onScreen = Boolean(entry?.isIntersecting && entry.intersectionRatio >= 0.35);
        sync();
      },
      { root: scroller instanceof Element ? scroller : null, threshold: [0, 0.35, 0.7] },
    );
    observer.observe(root);

    function sync() {
      if (!root) {
        return;
      }
      const paused = document.hidden || !onScreen || reduce.matches;
      root.classList.toggle("hero-paused", paused && !reduce.matches);
    }
    document.addEventListener("visibilitychange", sync);
    sync();

    return () => {
      reduce.removeEventListener("change", applyReduce);
      observer.disconnect();
      document.removeEventListener("visibilitychange", sync);
    };
  }, []);

  return (
    <div className="hero-anim" ref={rootRef}>
      <svg className="hero-svg" viewBox="0 0 1000 640" role="img" aria-hidden="true">
        <g className="hero-dash">
          <rect className="hero-shell" x="16" y="16" width="968" height="608" rx="16" />
          <rect className="hero-side" x="16" y="16" width="196" height="608" />
          <image
            href="/brand/sentinel-wordmark-white.png"
            x="36"
            y="40"
            width="156"
            height="36"
            preserveAspectRatio="xMidYMid meet"
          />
          <rect className="hero-nav-on" x="36" y="112" width="148" height="28" rx="6" />
          <rect className="hero-nav" x="36" y="152" width="132" height="28" rx="6" />
          <rect className="hero-nav" x="36" y="192" width="116" height="28" rx="6" />
        </g>

        <svg className="hero-finder" viewBox="0 0 760 480" x="12%" y="12.5%" width="76%" height="75%">
          <rect className="hero-screen" width="760" height="480" />
          <g clipPath="url(#sentinel-hero-clip)">
            <rect className="hero-line" x="210" y="72" width="340" height="156" />
            <rect className="hero-line" x="338" y="104" width="84" height="124" />
            <circle className="hero-line" cx="406" cy="172" r="3" />
            <path className="hero-line" d="M36 110 L210 72 L210 228" />
            <path className="hero-line" d="M724 110 L550 72 L550 228" />
            <path className="hero-line" d="M36 452 L210 228 L550 228 L724 452" />
            <path className="hero-line" d="M380 228 L380 452" />
            <path className="hero-line" d="M140 318 L620 318" />
            <path className="hero-line" d="M88 388 L672 388" />
            <polygon className="hero-zone" points="488,246 700,268 678,432 456,408" />
            <polygon className="hero-zone-hot" points="488,246 700,268 678,432 456,408" />
            <text className="hero-intrusion" x="28" y="48">
              INTRUSIÓN
            </text>
            <Walker className="hero-walker hero-walker-a" />
            <Walker className="hero-walker hero-walker-b" />
            <g className="hero-scan">
              <line x1="20" y1="0" x2="740" y2="0" />
            </g>
          </g>
          <g className="hero-ticks">
            <path d="M18 46 V18 H46" />
            <path d="M714 18 H742 V46" />
            <path d="M18 434 V462 H46" />
            <path d="M714 462 H742 V434" />
          </g>
          <clipPath id="sentinel-hero-clip">
            <rect width="760" height="480" />
          </clipPath>
        </svg>

        <g className="hero-event">
          <rect className="hero-event-card" x="230" y="392" width="700" height="96" rx="12" />
          <rect className="hero-event-bar" x="230" y="392" width="10" height="96" />
          <text className="hero-event-copy" x="258" y="440" dominantBaseline="middle">
            INTRUSIÓN · ALTA · Acceso norte · ahora
          </text>
        </g>

        <g className="hero-phone">
          <rect className="hero-phone-body" x="748" y="40" width="176" height="312" rx="22" />
          <path className="hero-line" d="M812 58 H860" />
          <rect className="hero-phone-screen" x="764" y="76" width="144" height="248" rx="8" />
          <rect className="hero-note-card" x="776" y="96" width="120" height="92" rx="8" />
          <text className="hero-note-copy" x="786" y="132">
            SentinelAI:
          </text>
          <text className="hero-note-copy" x="786" y="158">
            nueva alerta
          </text>
        </g>

        <g className="hero-camera">
          <path className="hero-line" d="M28 18 H92" />
          <path className="hero-line" d="M60 18 V36" />
          <rect className="hero-line" x="18" y="36" width="86" height="48" rx="8" />
          <path className="hero-line" d="M104 48 L148 34 L148 86 L104 72 Z" />
          <circle className="hero-line" cx="132" cy="60" r="9" />
          <circle className="hero-led" cx="36" cy="52" r="4" />
        </g>
      </svg>
    </div>
  );
}
