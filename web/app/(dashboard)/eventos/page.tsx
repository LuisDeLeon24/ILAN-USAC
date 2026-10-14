"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { EventMotion } from "@/components/event-motion";
import { Frame, PageHeader } from "@/components/frame";
import { useMe } from "@/components/shell";
import { api, apiBlob } from "@/lib/api";
import { EVENT_LABELS, SEVERITY_LABELS, STATUS_LABELS, STATUS_MARKS, formatWhen, guatemalaDate } from "@/lib/labels";
import type { Camera, EventItem, EventStatus } from "@/lib/types";

const STATUSES: EventStatus[] = ["new", "in_review", "resolved", "false_positive"];

export default function EventsPage() {
  return (
    <Suspense fallback={null}>
      <EventsScreen />
    </Suspense>
  );
}

function EventsScreen() {
  const me = useMe();
  const focusId = useSearchParams().get("event") ?? "";
  const [rows, setRows] = useState<EventItem[]>([]);
  const [shownKey, setShownKey] = useState("");
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [start, setStart] = useState(() => guatemalaDate(-6));
  const [end, setEnd] = useState(() => guatemalaDate(0));
  const [eventType, setEventType] = useState("");
  const [severity, setSeverity] = useState("");
  const [cameraId, setCameraId] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!me) {
      return;
    }
    api<Camera[]>("/cameras")
      .then(setCameras)
      .catch(() => undefined);
  }, [me]);

  const requestKey = `${start}|${end}|${eventType}|${severity}|${cameraId}`;

  useEffect(() => {
    if (!focusId) {
      return;
    }
    setStart(guatemalaDate(-6));
    setEnd(guatemalaDate(0));
    setEventType("");
    setSeverity("");
    setCameraId("");
  }, [focusId]);

  useEffect(() => {
    if (!me) {
      return;
    }
    let active = true;
    const load = () => {
      const params = new URLSearchParams({ start, end });
      if (eventType) {
        params.set("event_type", eventType);
      }
      if (severity) {
        params.set("severity", severity);
      }
      if (cameraId) {
        params.set("camera_id", cameraId);
      }
      api<EventItem[]>(`/events?${params}`)
        .then((events) => {
          if (active) {
            setRows(events);
            setShownKey(requestKey);
            setError("");
          }
        })
        .catch((err: unknown) => {
          if (active) {
            setError(err instanceof Error ? err.message : "No se pudieron cargar los eventos");
          }
        });
    };
    load();
    const timer = window.setInterval(load, 5000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [me, requestKey, start, end, eventType, severity, cameraId]);

  useEffect(() => {
    if (!focusId || shownKey === "") {
      return;
    }
    const node = document.getElementById(`event-${focusId}`);
    if (!node) {
      return;
    }
    node.scrollIntoView({ block: "center" });
    node.focus({ preventScroll: true });
  }, [focusId, shownKey, rows]);

  async function changeStatus(event: EventItem, status: EventStatus) {
    if (status === event.status) {
      return;
    }
    setError("");
    try {
      const updated = await api<EventItem>(`/events/${event.id}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      setRows((current) => current.map((row) => (row.id === event.id ? { ...row, ...updated } : row)));
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo cambiar el estado");
    }
  }

  if (!me) {
    return null;
  }

  return (
    <>
      <PageHeader
        title="Eventos"
        subtitle="Historial"
        tagline="Filtra por fecha, tipo, severidad y cámara. El estado lo cambian administradores y operadores."
      />
      <Frame>
        <div className="stack">
          <div className="row">
            <label className="field">
              <span className="section-label">Desde</span>
              <input className="control" type="date" value={start} onChange={(event) => setStart(event.target.value)} />
            </label>
            <label className="field">
              <span className="section-label">Hasta</span>
              <input className="control" type="date" value={end} onChange={(event) => setEnd(event.target.value)} />
            </label>
            <label className="field">
              <span className="section-label">Tipo</span>
              <select className="control" value={eventType} onChange={(event) => setEventType(event.target.value)}>
                <option value="">Todos</option>
                {Object.entries(EVENT_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span className="section-label">Severidad</span>
              <select className="control" value={severity} onChange={(event) => setSeverity(event.target.value)}>
                <option value="">Todas</option>
                {Object.entries(SEVERITY_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span className="section-label">Cámara</span>
              <select className="control" value={cameraId} onChange={(event) => setCameraId(event.target.value)}>
                <option value="">Todas</option>
                {cameras.map((camera) => (
                  <option key={camera.id} value={camera.id}>
                    {camera.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {error ? <p className="form-error">{error}</p> : null}
          {shownKey === requestKey && rows.length === 0 ? (
            <p className="page-tagline">No hay eventos en este periodo.</p>
          ) : null}
          {shownKey === requestKey ? (
          <EventMotion items={rows} layout="stack" className="list" activeId={focusId}>
            {(event) => (
              <article
                id={`event-${event.id}`}
                tabIndex={-1}
                className={`event severity-${event.severity}${event.status === "false_positive" ? " is-false" : ""}`}
              >
                {event.has_snapshot ? <Snapshot id={event.id} label={EVENT_LABELS[event.event_type] ?? event.event_type} /> : null}
                <div>
                  <h2 className="card-title">{EVENT_LABELS[event.event_type] ?? event.event_type}</h2>
                  <p className="section-label">{SEVERITY_LABELS[event.severity] ?? event.severity}</p>
                  <p className={`card-meta status-label`}>
                    {STATUS_MARKS[event.status]} {STATUS_LABELS[event.status]}
                  </p>
                  <p className="card-meta">
                    {event.sensor_name ?? event.camera_name ?? "Sin origen"} · {formatWhen(event.occurred_at)}
                  </p>
                  <label className="field">
                    <span className="section-label">Estado</span>
                    <select
                      className="control status-select"
                      value={event.status}
                      onChange={(change) => changeStatus(event, change.target.value as EventStatus)}
                    >
                      {STATUSES.map((status) => (
                        <option key={status} value={status}>
                          {STATUS_MARKS[status]} {STATUS_LABELS[status]}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              </article>
            )}
          </EventMotion>
          ) : null}
        </div>
      </Frame>
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
