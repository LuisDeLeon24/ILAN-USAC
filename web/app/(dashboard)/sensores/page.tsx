"use client";

import { FormEvent, useEffect, useState } from "react";

import { Feedback, Field, Frame, PageHeader } from "@/components/frame";
import { useMe } from "@/components/shell";
import { Button } from "@/components/ui/button";
import { ApiError, api } from "@/lib/api";
import { SENSOR_TYPE_LABELS, formatWhen } from "@/lib/labels";
import type { SensorItem, SensorType, Site } from "@/lib/types";

const TYPES = Object.keys(SENSOR_TYPE_LABELS) as SensorType[];

export default function SensorsPage() {
  const me = useMe();
  const [rows, setRows] = useState<SensorItem[]>([]);
  const [sites, setSites] = useState<Site[]>([]);
  const [siteId, setSiteId] = useState("");
  const [name, setName] = useState("");
  const [sensorType, setSensorType] = useState<SensorType>("door");
  const [externalId, setExternalId] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function load() {
    const [sensors, siteRows] = await Promise.all([api<SensorItem[]>("/sensors"), api<Site[]>("/sites")]);
    setRows(sensors);
    setSites(siteRows);
    setSiteId((current) => current || siteRows[0]?.id || "");
  }

  useEffect(() => {
    if (!me) {
      return;
    }
    load().catch((err: unknown) => setError(err instanceof Error ? err.message : "No se pudieron cargar los sensores"));
  }, [me]);

  if (!me) {
    return null;
  }

  function resetForm() {
    setName("");
    setSensorType("door");
    setExternalId("");
    setEditing(null);
    setSiteId(sites[0]?.id || "");
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError("");
    const payload = { site_id: siteId, name, sensor_type: sensorType, external_id: externalId };
    try {
      if (editing) {
        await api(`/sensors/${editing}`, { method: "PATCH", body: JSON.stringify(payload) });
      } else {
        await api("/sensors", { method: "POST", body: JSON.stringify(payload) });
      }
      resetForm();
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo guardar el sensor");
    } finally {
      setPending(false);
    }
  }

  async function remove(id: string) {
    setPending(true);
    setError("");
    try {
      await api(`/sensors/${id}`, { method: "DELETE" });
      if (editing === id) {
        resetForm();
      }
      setConfirming(null);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo eliminar el sensor");
    } finally {
      setPending(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Sensores"
        subtitle="Lecturas de la instalación"
        tagline="Puertas, movimiento, humo y pánico entran por el dispositivo en sitio."
      />
      <Frame>
        <div className="stack">
          {me.role === "admin" ? (
            <form className="stack" onSubmit={onSubmit}>
              <Field label="Sitio">
                <select className="control" value={siteId} onChange={(event) => setSiteId(event.target.value)} required>
                  {sites.length === 0 ? <option value="">Sin sitios</option> : null}
                  {sites.map((site) => (
                    <option key={site.id} value={site.id}>
                      {site.name}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Nombre">
                <input className="control" value={name} onChange={(event) => setName(event.target.value)} required />
              </Field>
              <Field label="Tipo">
                <select
                  className="control"
                  value={sensorType}
                  onChange={(event) => setSensorType(event.target.value as SensorType)}
                >
                  {TYPES.map((value) => (
                    <option key={value} value={value}>
                      {SENSOR_TYPE_LABELS[value]}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label="Identificador externo">
                <input
                  className="control"
                  value={externalId}
                  placeholder="puerta-bodega"
                  onChange={(event) => setExternalId(event.target.value)}
                  required
                />
              </Field>
              <p className="card-meta">El simulador y el panel local envían este identificador al dispositivo en sitio.</p>
              <div className="actions">
                <Button type="submit" variant="primary" disabled={pending || !siteId}>
                  {pending ? "Guardando…" : editing ? "Guardar cambios" : "Guardar sensor"}
                </Button>
                {editing ? (
                  <Button type="button" onClick={resetForm}>
                    Cancelar
                  </Button>
                ) : null}
              </div>
            </form>
          ) : null}
          <Feedback message={error} />
          {rows.length === 0 ? <p className="page-tagline">Aún no hay sensores.</p> : null}
          <div className="list">
            {rows.map((sensor) => (
              <article className="item" key={sensor.id}>
                <h2 className="card-title">{sensor.name}</h2>
                <p className="card-meta">
                  {SENSOR_TYPE_LABELS[sensor.sensor_type] ?? sensor.sensor_type} · {formatWhen(sensor.created_at)}
                </p>
                <p className="card-meta">Identificador: {sensor.external_id}</p>
                {me.role === "admin" ? (
                  confirming === sensor.id ? (
                    <div className="actions">
                      <span className="card-meta">¿Eliminar este sensor?</span>
                      <Button type="button" onClick={() => remove(sensor.id)} disabled={pending}>
                        Eliminar
                      </Button>
                      <Button type="button" onClick={() => setConfirming(null)}>
                        Cancelar
                      </Button>
                    </div>
                  ) : (
                    <div className="actions">
                      <Button
                        type="button"
                        onClick={() => {
                          setEditing(sensor.id);
                          setSiteId(sensor.site_id);
                          setName(sensor.name);
                          setSensorType(sensor.sensor_type);
                          setExternalId(sensor.external_id);
                          setConfirming(null);
                        }}
                      >
                        Editar
                      </Button>
                      <Button type="button" onClick={() => setConfirming(sensor.id)}>
                        Eliminar
                      </Button>
                    </div>
                  )
                ) : null}
              </article>
            ))}
          </div>
        </div>
      </Frame>
    </>
  );
}
