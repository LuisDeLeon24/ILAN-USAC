"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { EventMotion } from "@/components/event-motion";
import { PageHeader } from "@/components/frame";
import { useMe } from "@/components/shell";
import { Button } from "@/components/ui/button";
import { api, apiBlob } from "@/lib/api";
import { consumePreview } from "@/lib/mjpeg";
import { EVENT_LABELS, SEVERITY_LABELS, countLabel, formatWhen, guatemalaDate } from "@/lib/labels";
import type { Camera, EventItem } from "@/lib/types";

type LiveTicket = {
  token: string;
  expires_at: string;
  stream_url: string;
  status_url: string;
};

type LiveStatus = {
  signal: boolean;
  fps: number;
  people: number;
};

const TOKEN_REFRESH_MS = 4 * 60 * 1000;
const STATUS_POLL_MS = 1000;
const EVENT_POLL_MS = 3000;
const STREAM_RETRY_AFTER_ERROR_MS = 1000;

export default function CameraLivePage() {
  const me = useMe();
  const params = useParams<{ id: string }>();
  const cameraId = Array.isArray(params.id) ? params.id[0] : params.id;
  const [camera, setCamera] = useState<Camera | null>(null);
  const [streamUrl, setStreamUrl] = useState("");
  const [statusUrl, setStatusUrl] = useState("");
  const [ready, setReady] = useState(false);
  const [status, setStatus] = useState<LiveStatus | null>(null);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [eventsReady, setEventsReady] = useState(false);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [override, setOverride] = useState<boolean | null>(null);
  const [frameUrl, setFrameUrl] = useState("");

  useEffect(() => {
    if (!me || !cameraId) {
      return;
    }
    api<Camera>(`/cameras/${cameraId}`)
      .then(setCamera)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "No se pudo cargar la cámara"));
  }, [me, cameraId]);

  const live = override ?? Boolean(camera?.enabled);

  useEffect(() => {
    if (!me || !cameraId || !live) {
      setStreamUrl("");
      setStatusUrl("");
      setStatus(null);
      setReady(false);
      setFrameUrl("");
      return;
    }
    let stopped = false;
    let refreshTimer = 0;

    async function openStream() {
      try {
        const ticket = await api<LiveTicket>(`/cameras/${cameraId}/live-token`, { method: "POST" });
        if (stopped) {
          return;
        }
        const token = encodeURIComponent(ticket.token);
        setStreamUrl(`${ticket.stream_url}?token=${token}`);
        setStatusUrl(`${ticket.status_url}?token=${token}`);
        refreshTimer = window.setTimeout(() => {
          void openStream();
        }, TOKEN_REFRESH_MS);
      } catch {
        if (!stopped) {
          setStreamUrl("");
          setStatusUrl("");
          setReady(false);
          refreshTimer = window.setTimeout(() => {
            void openStream();
          }, STREAM_RETRY_AFTER_ERROR_MS);
        }
      }
    }

    setStreamUrl("");
    setStatusUrl("");
    setStatus(null);
    setReady(false);
    void openStream();
    return () => {
      stopped = true;
      window.clearTimeout(refreshTimer);
    };
  }, [me, cameraId, live]);

  useEffect(() => {
    if (!live || !streamUrl) {
      return;
    }
    const controller = new AbortController();
    let stopped = false;
    let currentUrl = "";
    const paint = (blob: Blob) => {
      const next = URL.createObjectURL(blob);
      const image = new Image();
      image.onload = () => {
        if (stopped) {
          URL.revokeObjectURL(next);
          return;
        }
        const previous = currentUrl;
        currentUrl = next;
        setFrameUrl(next);
        setReady(true);
        if (previous) {
          window.setTimeout(() => URL.revokeObjectURL(previous), STREAM_RETRY_AFTER_ERROR_MS);
        }
      };
      image.onerror = () => URL.revokeObjectURL(next);
      image.src = next;
    };
    const run = async () => {
      while (!stopped) {
        try {
          await consumePreview(streamUrl, controller.signal, paint, 0);
        } catch {
          if (stopped || controller.signal.aborted) {
            return;
          }
        }
        if (stopped || controller.signal.aborted) {
          return;
        }
        await new Promise((resolve) => window.setTimeout(resolve, STREAM_RETRY_AFTER_ERROR_MS));
      }
    };
    void run();
    return () => {
      stopped = true;
      controller.abort();
      if (currentUrl) {
        URL.revokeObjectURL(currentUrl);
      }
    };
  }, [live, streamUrl]);

  async function setAnalysis(enabled: boolean) {
    if (!camera || pending) {
      return;
    }
    setPending(true);
    setOverride(enabled);
    setError("");
    const body: { enabled: boolean; loop?: boolean } = { enabled };
    if (enabled && camera.source_type === "file") {
      body.loop = true;
    }
    try {
      const updated = await api<Camera>(`/cameras/${cameraId}`, { method: "PATCH", body: JSON.stringify(body) });
      setCamera(updated);
      setOverride(null);
    } catch (err) {
      setOverride(null);
      setError(err instanceof Error ? err.message : "No se pudo cambiar el análisis");
    } finally {
      setPending(false);
    }
  }

  useEffect(() => {
    if (!statusUrl) {
      return;
    }
    let active = true;
    const load = () => {
      fetch(statusUrl)
        .then(async (response) => {
          if (!response.ok) {
            throw new Error("sin señal");
          }
          return (await response.json()) as LiveStatus;
        })
        .then((next) => {
          if (active) {
            setStatus(next);
          }
        })
        .catch(() => {
          if (active) {
            setStatus((current) => current ?? { signal: false, fps: 0, people: 0 });
          }
        });
    };
    load();
    const timer = window.setInterval(load, STATUS_POLL_MS);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [statusUrl]);

  useEffect(() => {
    if (!me || !cameraId) {
      return;
    }
    let active = true;
    setEventsReady(false);
    const load = () => {
      const query = new URLSearchParams({
        start: guatemalaDate(-6),
        end: guatemalaDate(0),
        camera_id: cameraId,
      });
      api<EventItem[]>(`/events?${query}`)
        .then((rows) => {
          if (active) {
            setEvents(rows.slice(0, 8));
            setEventsReady(true);
          }
        })
        .catch(() => {
          if (active) {
            setEvents([]);
            setEventsReady(true);
          }
        });
    };
    load();
    const timer = window.setInterval(load, EVENT_POLL_MS);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [me, cameraId]);

  if (!me) {
    return null;
  }

  const hasFrames = ready && Boolean(frameUrl);
  const overlay = camera === null && override === null ? "" : live ? (hasFrames ? "" : "Conectando…") : "Cámara sin señal";

  return (
    <>
      <PageHeader
        title={camera?.name ?? "Cámara"}
        subtitle="En vivo"
        tagline="El video se queda en la red del sitio. El navegador se conecta al worker, no a la nube."
      />
      <div className="actions page-actions">
        <Link className="btn" href="/camaras">
          Volver a cámaras
        </Link>
        <Link className="btn" href={`/camaras/${cameraId}/zonas`}>
          Zonas
        </Link>
        <Link className="btn" href={`/camaras/${cameraId}/configuracion`}>
          Configuración
        </Link>
        {me.role === "admin" ? (
          <Button type="button" variant="primary" disabled={pending || !camera} onClick={() => void setAnalysis(!live)}>
            {live ? "Detener análisis" : "Iniciar análisis"}
          </Button>
        ) : null}
      </div>
      <div className="stage live-stage live-hero">
        {frameUrl ? (
          <img
            className="stage-image"
            src={frameUrl}
            alt={camera ? `Análisis en vivo de ${camera.name}` : "Análisis en vivo"}
            onLoad={() => setReady(true)}
          />
        ) : null}
        {overlay ? <p className="live-offline">{overlay}</p> : null}
        {hasFrames && status?.signal ? (
          <p className="live-indicator">
            Analizando · {status.fps} cuadros por segundo · {countLabel(status.people, "persona", "personas")}
          </p>
        ) : null}
      </div>
      {error ? <p className="form-error">{error}</p> : null}
      <section className="event-strip">
        <h2 className="card-title">Últimos eventos</h2>
        {eventsReady && events.length === 0 ? <p className="card-meta">Esta cámara no tiene eventos recientes.</p> : null}
        {eventsReady ? (
          <EventMotion items={events} layout="row" className="event-row">
            {(event) => (
              <article className={`event event-card severity-${event.severity}`}>
                {event.has_snapshot ? <Snapshot id={event.id} label={EVENT_LABELS[event.event_type] ?? event.event_type} /> : <div className="thumb" />}
                <h3 className="card-title">{EVENT_LABELS[event.event_type] ?? event.event_type}</h3>
                <p className="section-label">{SEVERITY_LABELS[event.severity] ?? event.severity}</p>
                <p className="card-meta">{formatWhen(event.occurred_at)}</p>
              </article>
            )}
          </EventMotion>
        ) : null}
      </section>
    </>
  );
}

function Snapshot({ id, label }: { id: string; label: string }) {
  const [url, setUrl] = useState("");

  useEffect(() => {
    let active = true;
    let objectUrl = "";
    apiBlob(`/events/${id}/snapshot`)
      .then((value) => {
        objectUrl = value;
        if (active) {
          setUrl(value);
        } else {
          URL.revokeObjectURL(value);
        }
      })
      .catch(() => undefined);
    return () => {
      active = false;
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [id]);

  if (!url) {
    return <div className="thumb" />;
  }
  return <img className="thumb" src={url} alt={`Captura de ${label}`} />;
}
