"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { CameraForm } from "@/components/camera-form";
import { Feedback, Frame, PageHeader } from "@/components/frame";
import { useMe } from "@/components/shell";
import { Button } from "@/components/ui/button";
import { ApiError, api } from "@/lib/api";
import type { Camera, Site } from "@/lib/types";

export default function CameraSettingsPage() {
  const me = useMe();
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const cameraId = Array.isArray(params.id) ? params.id[0] : params.id;
  const [camera, setCamera] = useState<Camera | null>(null);
  const [sites, setSites] = useState<Site[]>([]);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (!me || !cameraId) {
      return;
    }
    Promise.all([api<Camera>(`/cameras/${cameraId}`), api<Site[]>("/sites")])
      .then(([cameraRow, siteRows]) => {
        setCamera(cameraRow);
        setSites(siteRows);
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "No se pudo cargar la cámara"));
  }, [me, cameraId]);

  if (!me) {
    return null;
  }

  async function remove() {
    setPending(true);
    setError("");
    try {
      await api(`/cameras/${cameraId}`, { method: "DELETE" });
      router.push("/camaras");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo eliminar la cámara");
      setPending(false);
    }
  }

  const admin = me.role === "admin";

  return (
    <>
      <PageHeader
        title="Configuración"
        subtitle={camera?.name ?? "Cámara"}
        tagline="Fuente, velocidad de análisis y sensibilidad de esta cámara."
      />
      <div className="actions page-actions">
        <Link className="btn" href={`/camaras/${cameraId}`}>
          Volver a la cámara
        </Link>
      </div>
      <Frame>
        <div className="stack">
          {camera ? (
            <CameraForm
              key={camera.id}
              sites={sites}
              camera={camera}
              readOnly={!admin}
              onSaved={() => router.push(`/camaras/${cameraId}`)}
            />
          ) : null}
          <Feedback message={error} />
          {admin && camera ? (
            <div className="actions">
              {confirming ? (
                <>
                  <span className="card-meta">¿Eliminar esta cámara y sus zonas?</span>
                  <Button type="button" onClick={() => void remove()} disabled={pending}>
                    Eliminar
                  </Button>
                  <Button type="button" onClick={() => setConfirming(false)}>
                    Cancelar
                  </Button>
                </>
              ) : (
                <Button type="button" onClick={() => setConfirming(true)}>
                  Eliminar
                </Button>
              )}
            </div>
          ) : null}
        </div>
      </Frame>
    </>
  );
}
