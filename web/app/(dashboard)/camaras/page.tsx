"use client";

import { useEffect, useState } from "react";

import { CameraCard, cameraTodayCount, latestSnapshotId } from "@/components/camera-card";
import { CameraForm } from "@/components/camera-form";
import { Feedback, Frame, PageHeader } from "@/components/frame";
import { useMe } from "@/components/shell";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { Camera, EventItem, Site } from "@/lib/types";

export default function CamerasPage() {
  const me = useMe();
  const [sites, setSites] = useState<Site[]>([]);
  const [rows, setRows] = useState<Camera[]>([]);
  const [events, setEvents] = useState<EventItem[]>([]);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    const [siteRows, cameraRows, eventRows] = await Promise.all([
      api<Site[]>("/sites"),
      api<Camera[]>("/cameras"),
      api<EventItem[]>("/events").catch(() => [] as EventItem[]),
    ]);
    setSites(siteRows);
    setRows(cameraRows);
    setEvents(eventRows);
  }

  useEffect(() => {
    if (!me) {
      return;
    }
    load().catch((err: unknown) => setError(err instanceof Error ? err.message : "No se pudieron cargar las cámaras"));
  }, [me]);

  if (!me) {
    return null;
  }

  const siteName = (id: string) => sites.find((site) => site.id === id)?.name ?? "Sitio";
  const ordered = [...rows].sort((left, right) => left.name.localeCompare(right.name, "es"));

  return (
    <>
      <PageHeader
        title="Cámaras"
        subtitle="Fuentes de video"
        tagline="Cámaras conectadas a SentinelAI. Selecciona una para verla en vivo."
      />
      {me.role === "admin" && !adding ? (
        <div className="actions page-actions">
          <Button type="button" variant="primary" onClick={() => setAdding(true)}>
            Agregar cámara
          </Button>
        </div>
      ) : null}
      {adding && me.role === "admin" ? (
        <Frame className="page-panel">
          <div className="stack">
            {sites.length === 0 ? (
              <>
                <p className="page-tagline">Crea un sitio antes de registrar una cámara.</p>
                <div className="actions">
                  <Button type="button" onClick={() => setAdding(false)}>
                    Cancelar
                  </Button>
                </div>
              </>
            ) : (
              <CameraForm
                sites={sites}
                onSaved={() => {
                  setAdding(false);
                  load().catch((err: unknown) => setError(err instanceof Error ? err.message : "No se pudieron cargar las cámaras"));
                }}
                onCancel={() => setAdding(false)}
              />
            )}
          </div>
        </Frame>
      ) : null}
      <Feedback message={error} />
      {rows.length === 0 ? <p className="page-tagline">Aún no hay cámaras.</p> : null}
      <div className="camera-grid">
        {ordered.map((camera) => (
          <CameraCard
            key={camera.id}
            camera={camera}
            siteName={siteName(camera.site_id)}
            todayCount={cameraTodayCount(events, camera.id)}
            snapshotEventId={latestSnapshotId(events, camera.id)}
          />
        ))}
      </div>
    </>
  );
}
