"use client";

import { FormEvent, KeyboardEvent, PointerEvent as ReactPointerEvent, useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { animated, useSpring } from "@react-spring/web";

import { Button } from "@/components/ui/button";
import { auroraSpring } from "@/lib/motion";

const EXAMPLES = [
  "¿Cuántas intrusiones hubo esta semana?",
  "Resume los eventos críticos de ayer",
  "¿Cuántos minutos se analizaron este mes y cuál es el costo estimado?",
];

const NOTE_KEY = "senti_dictation_note";
const HOLD_MS = 650;
const IDLE_GLOW = 0.45;
const PULSE_GLOW = 0.72;
const PEAK_GLOW = 1;
const FAN_RATIO = 0.45;

type SpeechResult = {
  isFinal: boolean;
  0: { transcript: string };
};

type SpeechEvent = {
  resultIndex: number;
  results: ArrayLike<SpeechResult>;
};

type SpeechError = { error: string };

type BrowserSpeech = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((event: SpeechEvent) => void) | null;
  onerror: ((event: SpeechError) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};

type SpeechCtor = new () => BrowserSpeech;

type SiteOption = { id: string; name: string };

function speechCtor(): SpeechCtor | null {
  if (typeof window === "undefined") {
    return null;
  }
  const host = window as Window & { SpeechRecognition?: SpeechCtor; webkitSpeechRecognition?: SpeechCtor };
  return host.SpeechRecognition || host.webkitSpeechRecognition || null;
}

function tokenOpacity(name: string, fallback: number): number {
  if (typeof window === "undefined") {
    return fallback;
  }
  const raw = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const value = Number(raw);
  return raw.length > 0 && Number.isFinite(value) ? value : fallback;
}

function MicIcon() {
  return (
    <svg className="senti-glyph" viewBox="0 0 24 24" aria-hidden="true">
      <rect x="9" y="3" width="6" height="11" rx="3" fill="none" stroke="currentColor" strokeWidth="2" />
      <path
        d="M6 11a6 6 0 0 0 12 0M12 17v4M8 21h8"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    const apply = () => setReduced(media.matches);
    apply();
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, []);
  return reduced;
}

export function SentiComposer({
  value,
  onChange,
  onSubmit,
  onReset,
  pending,
  sites,
  siteId,
  onSite,
  emphasis,
  onNotice,
}: {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (value: string) => void;
  onReset: () => void;
  pending: boolean;
  sites: SiteOption[];
  siteId: string;
  onSite: (siteId: string) => void;
  emphasis: boolean;
  onNotice: (message: string) => void;
}) {
  const menuId = useId();
  const formRef = useRef<HTMLFormElement>(null);
  const fieldRef = useRef<HTMLTextAreaElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const session = useRef<BrowserSpeech | null>(null);
  const base = useRef("");
  const hold = useRef<number | null>(null);
  const held = useRef(false);
  const [open, setOpen] = useState(false);
  const [speechOn, setSpeechOn] = useState(false);
  const [note, setNote] = useState(false);
  const [listening, setListening] = useState(false);
  const reduced = useReducedMotion();
  const [glow, setGlow] = useState({ idle: IDLE_GLOW, pulse: PULSE_GLOW, peak: PEAK_GLOW });
  const [fan, setFan] = useState(0);

  useEffect(() => {
    setGlow({
      idle: tokenOpacity("--opacity-aurora-idle", IDLE_GLOW),
      pulse: tokenOpacity("--opacity-aurora-pulse", PULSE_GLOW),
      peak: tokenOpacity("--opacity-aurora-active", PEAK_GLOW),
    });
    const supported = speechCtor() !== null;
    setSpeechOn(supported);
    if (supported && window.localStorage.getItem(NOTE_KEY) !== "1") {
      setNote(true);
    }
  }, []);

  useEffect(() => {
    if (!open) {
      return;
    }
    function onPointer(event: PointerEvent) {
      if (!menuRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function onKey(event: globalThis.KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
      }
    }
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  useEffect(() => {
    return () => {
      session.current?.stop();
      if (hold.current !== null) {
        window.clearTimeout(hold.current);
      }
    };
  }, []);

  useLayoutEffect(() => {
    const field = fieldRef.current;
    if (field) {
      field.style.height = "auto";
      const max = Number.parseFloat(getComputedStyle(field).maxHeight);
      const next = Number.isFinite(max) ? Math.min(field.scrollHeight, max) : field.scrollHeight;
      field.style.height = `${next}px`;
    }
    const form = formRef.current;
    if (!form) {
      return;
    }
    const raw = getComputedStyle(form).getPropertyValue("--aurora-height");
    const pct = Number.parseFloat(raw);
    const ratio = Number.isFinite(pct) ? pct / 100 : FAN_RATIO;
    setFan(form.clientHeight * ratio);
  }, [value, pending]);

  const active = pending && !reduced;
  const motion = useSpring({
    from: { shift: -1, alpha: glow.pulse },
    to: { shift: active ? 1 : 0, alpha: active ? glow.peak : glow.idle },
    loop: active ? { reverse: true } : false,
    immediate: !active,
    config: auroraSpring,
  });

  function dismissNote() {
    window.localStorage.setItem(NOTE_KEY, "1");
    setNote(false);
  }

  function startRecognition(lang: string, allowFallback: boolean) {
    const Ctor = speechCtor();
    if (!Ctor) {
      return;
    }
    const recognition = new Ctor();
    recognition.lang = lang;
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.onresult = (event) => {
      let spoken = "";
      for (let index = 0; index < event.results.length; index += 1) {
        spoken += event.results[index][0]?.transcript ?? "";
      }
      const prefix = base.current;
      onChange([prefix, spoken.trim()].filter(Boolean).join(" "));
    };
    recognition.onerror = (event) => {
      if (allowFallback && event.error === "language-not-supported") {
        if (session.current === recognition) {
          session.current = null;
        }
        startRecognition("es-ES", false);
        return;
      }
      if (event.error === "aborted") {
        return;
      }
      onNotice("No se pudo dictar. Revisa el permiso del micrófono.");
      if (session.current === recognition) {
        setListening(false);
      }
    };
    recognition.onend = () => {
      if (session.current === recognition) {
        session.current = null;
        setListening(false);
      }
    };
    try {
      recognition.start();
      session.current = recognition;
      setListening(true);
    } catch {
      if (allowFallback) {
        startRecognition("es-ES", false);
      } else {
        onNotice("No se pudo dictar. Revisa el permiso del micrófono.");
      }
    }
  }

  function onMic() {
    if (session.current) {
      session.current.stop();
      return;
    }
    if (note) {
      dismissNote();
    }
    base.current = value.trim();
    startRecognition("es-GT", true);
  }

  function clearHold() {
    if (hold.current !== null) {
      window.clearTimeout(hold.current);
      hold.current = null;
    }
  }

  function startHold(event: ReactPointerEvent<HTMLButtonElement>) {
    if (pending || event.button !== 0) {
      return;
    }
    held.current = false;
    clearHold();
    hold.current = window.setTimeout(() => {
      held.current = true;
      setOpen(false);
      onReset();
    }, HOLD_MS);
  }

  function onClear() {
    if (held.current) {
      held.current = false;
      return;
    }
    onChange("");
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    setOpen(false);
    onSubmit(value);
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      setOpen(false);
      onSubmit(value);
    }
  }

  return (
    <div className="senti-stack">
      {note ? (
        <p className="senti-note">
          La dictación puede ser procesada por el proveedor del navegador.
          <button className="chip" type="button" onClick={dismissNote}>
            Entendido
          </button>
        </p>
      ) : null}
      <form className="senti-composer" ref={formRef} data-state={pending ? "thinking" : "idle"} onSubmit={submit}>
        <animated.div
          className="senti-aurora"
          aria-hidden="true"
          style={{
            opacity: motion.alpha,
            height: fan > 0 ? fan : undefined,
            ["--aurora-drift-unit" as string]: motion.shift.to((shift) => `${shift}`),
          }}
        />
        <textarea
          ref={fieldRef}
          className="senti-field"
          value={value}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Pregúntale a Senti…"
          aria-label="Pregunta"
          rows={1}
          disabled={pending}
        />
        <div className="senti-tools" ref={menuRef}>
          {open ? (
            <div className="senti-menu" id={menuId} role="menu">
              {EXAMPLES.map((example) => (
                <button
                  className="senti-menu-item"
                  key={example}
                  type="button"
                  role="menuitem"
                  disabled={pending}
                  onClick={() => {
                    setOpen(false);
                    onSubmit(example);
                  }}
                >
                  {example}
                </button>
              ))}
              <button
                className="senti-menu-item senti-menu-reset"
                type="button"
                role="menuitem"
                disabled={pending}
                onClick={() => {
                  setOpen(false);
                  onReset();
                }}
              >
                Nueva conversación
              </button>
            </div>
          ) : null}
          <button
            className="senti-icon"
            type="button"
            aria-label="Preguntas sugeridas"
            aria-expanded={open}
            aria-controls={menuId}
            disabled={pending}
            onClick={() => setOpen((current) => !current)}
          >
            +
          </button>
          <select
            className="senti-scope"
            aria-label="Sitio"
            value={siteId}
            disabled={pending}
            onChange={(event) => onSite(event.target.value)}
          >
            <option value="">Todos los sitios</option>
            {sites.map((site) => (
              <option key={site.id} value={site.id}>
                {site.name}
              </option>
            ))}
          </select>
          {speechOn ? (
            <button
              className="senti-icon"
              type="button"
              aria-label=              {listening ? "Detener dictado" : "Dictar"}
              aria-pressed={listening}
              disabled={pending}
              onClick={onMic}
            >
              <MicIcon />
            </button>
          ) : null}
          <button
            className="senti-icon"
            type="button"
            aria-label="Borrar el texto. Mantén pulsado para una conversación nueva."
            disabled={pending}
            onPointerDown={startHold}
            onPointerUp={clearHold}
            onPointerLeave={clearHold}
            onPointerCancel={clearHold}
            onContextMenu={(event) => event.preventDefault()}
            onClick={onClear}
          >
            ×
          </button>
          <Button className="senti-send" type="submit" variant={emphasis ? "primary" : "outline"} disabled={pending || !value.trim()}>
            {pending ? "Pensando…" : "Enviar"}
          </Button>
        </div>
      </form>
    </div>
  );
}
