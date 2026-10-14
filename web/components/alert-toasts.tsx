"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { animated, to, useTransition } from "@react-spring/web";

import { api } from "@/lib/api";
import { EVENT_LABELS, SEVERITY_LABELS, formatWhen, guatemalaDate } from "@/lib/labels";
import { slideFromCorner, spring } from "@/lib/motion";
import type { EventItem } from "@/lib/types";

const POLL_MS = 5000;
const DISMISS_MS = 6000;
const MAX_TOASTS = 3;
const ALERT_SEVERITIES = new Set(["high", "critical"]);

export function AlertToasts() {
  const router = useRouter();
  const [toasts, setToasts] = useState<EventItem[]>([]);

  const dismiss = useCallback((id: string) => {
    setToasts((current) => current.filter((item) => item.id !== id));
  }, []);

  const openEvent = useCallback(
    (id: string) => {
      dismiss(id);
      router.push(`/eventos?event=${encodeURIComponent(id)}`);
    },
    [dismiss, router],
  );

  useEffect(() => {
    let active = true;
    const seen = new Set<string>();
    let primed = false;

    const load = () => {
      const day = guatemalaDate(0);
      api<EventItem[]>(`/events?start=${day}&end=${day}`)
        .then((events) => {
          if (!active) {
            return;
          }
          if (!primed) {
            for (const event of events) {
              seen.add(event.id);
            }
            primed = true;
            return;
          }
          const fresh = events.filter((event) => !seen.has(event.id) && ALERT_SEVERITIES.has(event.severity));
          for (const event of events) {
            seen.add(event.id);
          }
          if (fresh.length === 0) {
            return;
          }
          setToasts((current) => {
            const existing = new Set(current.map((item) => item.id));
            const incoming = fresh.filter((event) => !existing.has(event.id));
            if (incoming.length === 0) {
              return current;
            }
            return [...incoming, ...current].slice(0, MAX_TOASTS);
          });
        })
        .catch(() => undefined);
    };

    load();
    const timer = window.setInterval(load, POLL_MS);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  const transitions = useTransition(toasts, {
    keys: (item) => item.id,
    from: { opacity: 0, x: 1, y: 1, span: 0 },
    enter: { opacity: 1, x: 0, y: 0, span: 1 },
    leave: { opacity: 0, x: 1, y: 1, span: 0 },
    config: spring,
  });

  return (
    <div className="alert-stack" aria-live="polite">
      {transitions((style, event) => (
        <animated.div
          className="alert-motion"
          style={{
            opacity: style.opacity,
            display: "grid",
            overflow: "hidden",
            gridTemplateRows: style.span.to((value: number) => `${value}fr`),
            transform: to([style.x, style.y], slideFromCorner),
          }}
        >
          <div className="event-motion-clip">
            <ToastCard event={event} onDismiss={dismiss} onOpen={openEvent} />
          </div>
        </animated.div>
      ))}
    </div>
  );
}

function ToastCard({
  event,
  onDismiss,
  onOpen,
}: {
  event: EventItem;
  onDismiss: (id: string) => void;
  onOpen: (id: string) => void;
}) {
  useEffect(() => {
    const timer = window.setTimeout(() => onDismiss(event.id), DISMISS_MS);
    return () => window.clearTimeout(timer);
  }, [event.id, onDismiss]);

  const source = event.camera_name ?? event.sensor_name ?? "Sin origen";

  return (
    <button type="button" className={`alert-toast severity-${event.severity}`} onClick={() => onOpen(event.id)}>
      <span className="card-title">{EVENT_LABELS[event.event_type] ?? event.event_type}</span>
      <span className="section-label">{SEVERITY_LABELS[event.severity] ?? event.severity}</span>
      <span className="card-meta">
        {source} · {formatWhen(event.occurred_at)}
      </span>
    </button>
  );
}
