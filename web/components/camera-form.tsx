"use client";

import { FormEvent, useState } from "react";

import { Feedback, Field } from "@/components/frame";
import { Button } from "@/components/ui/button";
import { ApiError, api } from "@/lib/api";
import type { Camera, Site } from "@/lib/types";

const CONFIDENCE = Array.from({ length: 19 }, (_, index) => ((index + 1) * 0.05).toFixed(2));

type Draft = {
  name: string;
  siteId: string;
  sourceType: "rtsp" | "file";
  rtspUrl: string;
  filePath: string;
  fps: string;
  enabled: boolean;
  loop: boolean;
  minConfidence: string;
  minBoxPercent: string;
};

function draftFrom(camera: Camera | null, siteId: string): Draft {
  if (!camera) {
    return {
      name: "",
      siteId,
      sourceType: "rtsp",
      rtspUrl: "",
      filePath: "/videos/demo1.mp4",
      fps: "2",
      enabled: true,
      loop: false,
      minConfidence: "0.35",
      minBoxPercent: "0",
    };
  }
  return {
    name: camera.name,
    siteId: camera.site_id,
    sourceType: camera.source_type,
    rtspUrl: "",
    filePath: camera.file_path ?? "",
    fps: String(camera.fps),
    enabled: camera.enabled,
    loop: camera.loop,
    minConfidence: camera.min_confidence.toFixed(2),
    minBoxPercent: String(Math.round(camera.min_box_area * 1000) / 10),
  };
}

export function CameraForm({
  sites,
  camera = null,
  readOnly = false,
  onSaved,
  onCancel,
}: {
  sites: Site[];
  camera?: Camera | null;
  readOnly?: boolean;
  onSaved: () => void;
  onCancel?: () => void;
}) {
  const [form, setForm] = useState<Draft>(() => draftFrom(camera, sites[0]?.id ?? ""));
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (readOnly) {
      return;
    }
    setPending(true);
    setError("");
    const payload: Record<string, unknown> = {
      name: form.name,
      site_id: form.siteId,
      source_type: form.sourceType,
      fps: Number(form.fps),
      enabled: form.enabled,
      min_confidence: Number(form.minConfidence),
      min_box_area: Number(form.minBoxPercent) / 100,
    };
    if (form.sourceType === "file") {
      payload.file_path = form.filePath.trim();
      payload.loop = form.loop;
    }
    if (form.sourceType === "rtsp" && form.rtspUrl.trim()) {
      payload.rtsp_url = form.rtspUrl.trim();
    }
    try {
      if (camera) {
        await api(`/cameras/${camera.id}`, { method: "PATCH", body: JSON.stringify(payload) });
      } else {
        await api("/cameras", { method: "POST", body: JSON.stringify(payload) });
      }
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo guardar la cámara");
    } finally {
      setPending(false);
    }
  }

  return (
    <form className="stack" onSubmit={onSubmit}>
      <Field label="Nombre">
        <input
          className="control"
          value={form.name}
          onChange={(event) => setForm({ ...form, name: event.target.value })}
          required
          disabled={readOnly}
        />
      </Field>
      <Field label="Sitio">
        <select
          className="control"
          value={form.siteId}
          onChange={(event) => setForm({ ...form, siteId: event.target.value })}
          disabled={readOnly}
        >
          {sites.map((site) => (
            <option key={site.id} value={site.id}>
              {site.name}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Tipo de fuente">
        <select
          className="control"
          value={form.sourceType}
          onChange={(event) => setForm({ ...form, sourceType: event.target.value as "rtsp" | "file" })}
          disabled={readOnly}
        >
          <option value="rtsp">RTSP</option>
          <option value="file">Archivo</option>
        </select>
      </Field>
      {form.sourceType === "rtsp" ? (
        <Field label="URL RTSP">
          <input
            className="control"
            value={form.rtspUrl}
            placeholder={camera ? "Deja en blanco para conservar la actual" : "rtsp://usuario:clave@host:554/stream"}
            autoComplete="off"
            onChange={(event) => setForm({ ...form, rtspUrl: event.target.value })}
            required={!camera}
            disabled={readOnly}
          />
        </Field>
      ) : (
        <>
          <Field label="Ruta del archivo">
            <input
              className="control"
              value={form.filePath}
              placeholder="/videos/demo1.mp4"
              onChange={(event) => setForm({ ...form, filePath: event.target.value })}
              required
              disabled={readOnly}
            />
          </Field>
          <div className="field">
            <span className="section-label">Repetir en bucle</span>
            <button
              type="button"
              className={form.loop ? "chip on" : "chip"}
              onClick={() => setForm({ ...form, loop: !form.loop })}
              disabled={readOnly}
            >
              {form.loop ? "Activo" : "Una sola vez"}
            </button>
            <p className="card-meta">Cada vuelta cuenta como tiempo de video analizado.</p>
          </div>
        </>
      )}
      <Field label="Confianza mínima">
        <select
          className="control"
          value={form.minConfidence}
          onChange={(event) => setForm({ ...form, minConfidence: event.target.value })}
          disabled={readOnly}
        >
          {CONFIDENCE.map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Tamaño mínimo del recuadro (%)">
        <input
          className="control"
          type="number"
          min="0"
          max="100"
          step="0.1"
          value={form.minBoxPercent}
          onChange={(event) => setForm({ ...form, minBoxPercent: event.target.value })}
          required
          disabled={readOnly}
        />
      </Field>
      <p className="card-meta">
        0 no descarta detecciones por tamaño. Un valor más alto ignora recuadros pequeños, como reflejos lejanos.
      </p>
      <Field label="Cuadros por segundo">
        <select
          className="control"
          value={form.fps}
          onChange={(event) => setForm({ ...form, fps: event.target.value })}
          disabled={readOnly}
        >
          {["2", "3", "4", "5"].map((value) => (
            <option key={value} value={value}>
              {value}
            </option>
          ))}
        </select>
      </Field>
      <div className="field">
        <span className="section-label">Estado</span>
        <button
          type="button"
          className={form.enabled ? "chip on" : "chip"}
          onClick={() => setForm({ ...form, enabled: !form.enabled })}
          disabled={readOnly}
        >
          {form.enabled ? "Activa" : "Inactiva"}
        </button>
      </div>
      <p className="card-meta">Las credenciales RTSP se guardan cifradas.</p>
      <Feedback message={error} />
      {readOnly ? null : (
        <div className="actions">
          <Button type="submit" variant="primary" disabled={pending}>
            {pending ? "Guardando…" : camera ? "Guardar cambios" : "Guardar cámara"}
          </Button>
          {onCancel ? (
            <Button type="button" onClick={onCancel}>
              Cancelar
            </Button>
          ) : null}
        </div>
      )}
    </form>
  );
}
