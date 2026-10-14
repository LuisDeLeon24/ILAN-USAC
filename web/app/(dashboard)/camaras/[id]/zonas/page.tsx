"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { Feedback, Field, Frame, PageHeader } from "@/components/frame";
import { PolygonEditor } from "@/components/polygon-editor";
import { useMe } from "@/components/shell";
import { Button } from "@/components/ui/button";
import { ApiError, api, apiBlob } from "@/lib/api";
import { DAY_OPTIONS, RULE_LABELS, formatWhen, scheduleCopy } from "@/lib/labels";
import type { Camera, Exclusion, Zone } from "@/lib/types";

const ALL_DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];

export default function ZonesPage() {
  const me = useMe();
  const params = useParams<{ id: string }>();
  const cameraId = Array.isArray(params.id) ? params.id[0] : params.id;
  const [camera, setCamera] = useState<Camera | null>(null);
  const [rows, setRows] = useState<Zone[]>([]);
  const [exclusions, setExclusions] = useState<Exclusion[]>([]);
  const [name, setName] = useState("");
  const [points, setPoints] = useState<number[][]>([]);
  const [closed, setClosed] = useState(false);
  const [mode, setMode] = useState<"zone" | "exclusion">("zone");
  const [days, setDays] = useState<string[]>(ALL_DAYS);
  const [start, setStart] = useState("00:00");
  const [end, setEnd] = useState("23:59");
  const [ruleType, setRuleType] = useState<Zone["rule_type"]>("intrusion");
  const [seconds, setSeconds] = useState("30");
  const [maxPeople, setMaxPeople] = useState("5");
  const [editing, setEditing] = useState<string | null>(null);
  const [editingExclusion, setEditingExclusion] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [frameUrl, setFrameUrl] = useState("");
  const [frameNote, setFrameNote] = useState("");
  const [waiting, setWaiting] = useState(false);
  const [requestNonce, setRequestNonce] = useState(0);

  async function load() {
    const [cameraRow, zoneRows, exclusionRows] = await Promise.all([
      api<Camera>(`/cameras/${cameraId}`),
      api<Zone[]>(`/cameras/${cameraId}/zones`),
      api<Exclusion[]>(`/cameras/${cameraId}/exclusions`),
    ]);
    setCamera(cameraRow);
    setRows(zoneRows);
    setExclusions(exclusionRows);
  }

  useEffect(() => {
    if (!me || !cameraId) {
      return;
    }
    load().catch((err: unknown) => setError(err instanceof Error ? err.message : "No se pudieron cargar las zonas"));
  }, [me, cameraId]);

  useEffect(() => {
    if (!me || !cameraId) {
      return;
    }
    let cancelled = false;
    let timer = 0;
    const urls: string[] = [];
    const remember = (url: string) => {
      urls.push(url);
      setFrameUrl((current) => {
        if (current) {
          URL.revokeObjectURL(current);
        }
        return url;
      });
    };
    const poll = (deadline: number) => {
      if (cancelled) {
        return;
      }
      apiBlob(`/cameras/${cameraId}/frame`)
        .then((url) => {
          if (cancelled) {
            URL.revokeObjectURL(url);
            return;
          }
          remember(url);
          setFrameNote("El cuadro caduca a los 10 minutos.");
          setWaiting(false);
        })
        .catch(() => {
          if (cancelled) {
            return;
          }
          if (Date.now() > deadline) {
            setWaiting(false);
            setFrameNote("El dispositivo aún no envió un cuadro. Puede tardar unos 20 segundos.");
            return;
          }
          timer = window.setTimeout(() => poll(deadline), 2000);
        });
    };
    if (me.role === "admin") {
      setWaiting(true);
      setFrameNote("Solicitando cuadro…");
      setFrameUrl("");
      api(`/cameras/${cameraId}/frame-request`, { method: "POST" })
        .then(() => {
          if (!cancelled) {
            poll(Date.now() + 45000);
          }
        })
        .catch((err: unknown) => {
          if (!cancelled) {
            setWaiting(false);
            setFrameNote(err instanceof Error ? err.message : "No se pudo solicitar el cuadro");
          }
        });
    } else {
      apiBlob(`/cameras/${cameraId}/frame`)
        .then((url) => {
          if (cancelled) {
            URL.revokeObjectURL(url);
            return;
          }
          remember(url);
          setFrameNote("El cuadro caduca a los 10 minutos.");
        })
        .catch(() => {
          if (!cancelled) {
            setFrameNote("");
          }
        });
    }
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
      urls.forEach((url) => URL.revokeObjectURL(url));
    };
  }, [me, cameraId, requestNonce]);

  if (!me) {
    return null;
  }

  function resetDraft() {
    setName("");
    setPoints([]);
    setClosed(false);
    setDays(ALL_DAYS);
    setStart("00:00");
    setEnd("23:59");
    setRuleType("intrusion");
    setSeconds("30");
    setMaxPeople("5");
    setEditing(null);
    setEditingExclusion(null);
  }

  function chooseMode(next: "zone" | "exclusion") {
    setMode(next);
    resetDraft();
    setError("");
  }

  function toggleDay(day: string) {
    setDays((current) => (current.includes(day) ? current.filter((item) => item !== day) : [...current, day]));
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    if (!closed || points.length < 3) {
      setError("Cierra el polígono antes de guardar. Necesita al menos 3 puntos.");
      return;
    }
    setPending(true);
    try {
      if (mode === "exclusion") {
        const payload = { polygon: points };
        if (editingExclusion) {
          await api(`/exclusions/${editingExclusion}`, { method: "PATCH", body: JSON.stringify(payload) });
        } else {
          await api(`/cameras/${cameraId}/exclusions`, { method: "POST", body: JSON.stringify(payload) });
        }
      } else {
        const payload = {
          name,
          polygon: points,
          schedule: { timezone: "America/Guatemala", windows: [{ days, start, end }] },
          rule_type: ruleType,
          rule_params: ruleType === "loitering" ? { seconds: Number(seconds) } : ruleType === "occupancy" ? { max_people: Number(maxPeople) } : {},
        };
        if (editing) {
          await api(`/zones/${editing}`, { method: "PATCH", body: JSON.stringify(payload) });
        } else {
          await api(`/cameras/${cameraId}/zones`, { method: "POST", body: JSON.stringify(payload) });
        }
      }
      resetDraft();
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo guardar");
    } finally {
      setPending(false);
    }
  }

  async function removeZone(id: string) {
    setPending(true);
    setError("");
    try {
      await api(`/zones/${id}`, { method: "DELETE" });
      if (editing === id) {
        resetDraft();
      }
      setConfirming(null);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo eliminar la zona");
    } finally {
      setPending(false);
    }
  }

  async function removeExclusion(id: string) {
    setPending(true);
    setError("");
    try {
      await api(`/exclusions/${id}`, { method: "DELETE" });
      if (editingExclusion === id) {
        resetDraft();
      }
      setConfirming(null);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo eliminar la exclusión");
    } finally {
      setPending(false);
    }
  }

  function describe(zone: Zone) {
    const slot = zone.schedule.windows[0];
    const extra =
      zone.rule_type === "loitering"
        ? ` · ${zone.rule_params.seconds} segundos`
        : zone.rule_type === "occupancy"
          ? ` · máximo ${zone.rule_params.max_people}`
          : "";
    const timing =
      zone.rule_type === "after_hours"
        ? `fuera de ${slot?.start ?? ""}–${slot?.end ?? ""}`
        : `activa ${slot?.start ?? ""}–${slot?.end ?? ""}`;
    return `${RULE_LABELS[zone.rule_type] ?? zone.rule_type}${extra} · ${timing} · ${zone.polygon.length} puntos`;
  }

  const admin = me.role === "admin";

  return (
    <>
      <PageHeader
        title="Zonas"
        subtitle={camera ? camera.name : "Cámara"}
        tagline="Dibuja la zona con el mouse sobre el cuadro. Las exclusiones ignoran vidrio y espejos. El cuadro solo sale del sitio cuando lo pides."
      />
      <Frame>
        <div className="stack">
          <div className="actions">
            <Link className="btn" href={`/camaras/${cameraId}`}>
              Volver a la cámara
            </Link>
            {admin ? (
              <Button type="button" onClick={() => setRequestNonce((value) => value + 1)} disabled={waiting}>
                {waiting ? "Esperando cuadro…" : "Actualizar cuadro"}
              </Button>
            ) : null}
          </div>
          {frameNote ? <p className="card-meta">{frameNote}</p> : null}
          <div className="split">
            <div className="stack">
              {admin ? (
                <div className="row">
                  <button type="button" className={mode === "zone" ? "chip on" : "chip"} onClick={() => chooseMode("zone")}>
                    Zona
                  </button>
                  <button type="button" className={mode === "exclusion" ? "chip on" : "chip"} onClick={() => chooseMode("exclusion")}>
                    Exclusión
                  </button>
                </div>
              ) : null}
              <PolygonEditor
                imageUrl={frameUrl}
                zones={rows.filter((zone) => zone.id !== editing)}
                exclusions={exclusions.filter((area) => area.id !== editingExclusion)}
                points={points}
                closed={closed}
                mode={mode}
                editable={admin}
                onChange={(next, isClosed) => {
                  setPoints(next);
                  setClosed(isClosed);
                }}
              />
              {admin ? (
                <div className="actions">
                  <Button
                    type="button"
                    onClick={() => {
                      if (!closed && points.length > 0) {
                        setPoints((current) => current.slice(0, -1));
                      }
                    }}
                    disabled={closed || points.length === 0}
                  >
                    Quitar último punto
                  </Button>
                  <Button type="button" onClick={() => setClosed(true)} disabled={closed || points.length < 3}>
                    {mode === "exclusion" ? "Cerrar exclusión" : "Cerrar zona"}
                  </Button>
                </div>
              ) : null}
            </div>
            <div className="stack">
              {admin ? (
                <form className="stack" onSubmit={onSubmit}>
                  {mode === "zone" ? (
                    <>
                      <Field label="Nombre">
                        <input className="control" value={name} onChange={(event) => setName(event.target.value)} required />
                      </Field>
                      <Field label="Tipo de regla">
                        <select className="control" value={ruleType} onChange={(event) => setRuleType(event.target.value as Zone["rule_type"])}>
                          {Object.entries(RULE_LABELS).map(([value, label]) => (
                            <option key={value} value={value}>
                              {label}
                            </option>
                          ))}
                        </select>
                      </Field>
                      <div className="field">
                        <span className="section-label">{scheduleCopy(ruleType).title}</span>
                        <p className="card-meta">{scheduleCopy(ruleType).help}</p>
                        <span className="section-label">{scheduleCopy(ruleType).days}</span>
                        <div className="row">
                          {DAY_OPTIONS.map(([value, label]) => (
                            <button
                              key={value}
                              type="button"
                              className={days.includes(value) ? "chip on" : "chip"}
                              onClick={() => toggleDay(value)}
                            >
                              {label}
                            </button>
                          ))}
                        </div>
                      </div>
                      <div className="row">
                        <Field label="Desde">
                          <input className="control" value={start} onChange={(event) => setStart(event.target.value)} required />
                        </Field>
                        <Field label="Hasta">
                          <input className="control" value={end} onChange={(event) => setEnd(event.target.value)} required />
                        </Field>
                      </div>
                      {ruleType === "loitering" ? (
                        <Field label="Segundos">
                          <input className="control" value={seconds} onChange={(event) => setSeconds(event.target.value)} required />
                        </Field>
                      ) : null}
                      {ruleType === "occupancy" ? (
                        <Field label="Máximo de personas">
                          <input className="control" value={maxPeople} onChange={(event) => setMaxPeople(event.target.value)} required />
                        </Field>
                      ) : null}
                    </>
                  ) : (
                    <p className="card-meta">
                      Un recuadro cuyo punto de apoyo cae dentro de la exclusión no genera eventos. Úsalo sobre vidrio o espejos.
                    </p>
                  )}
                  <div className="actions">
                    <Button type="submit" variant="primary" disabled={pending}>
                      {pending ? "Guardando…" : editing || editingExclusion ? "Guardar cambios" : mode === "exclusion" ? "Guardar exclusión" : "Guardar zona"}
                    </Button>
                    {editing || editingExclusion ? (
                      <Button type="button" onClick={resetDraft}>
                        Cancelar
                      </Button>
                    ) : null}
                  </div>
                </form>
              ) : null}
              <Feedback message={error} />
              <div className="list">
                {rows.length === 0 ? <p className="page-tagline">Aún no hay zonas.</p> : null}
                {rows.map((zone) => (
                  <article className="item" key={zone.id}>
                    <h2 className="card-title">{zone.name}</h2>
                    <p className="card-meta">{describe(zone)}</p>
                    <p className="card-meta">{formatWhen(zone.created_at)}</p>
                    {admin ? (
                      <div className="actions">
                        {confirming === zone.id ? (
                          <>
                            <span className="card-meta">¿Eliminar esta zona?</span>
                            <Button type="button" onClick={() => removeZone(zone.id)} disabled={pending}>
                              Eliminar
                            </Button>
                            <Button type="button" onClick={() => setConfirming(null)}>
                              Cancelar
                            </Button>
                          </>
                        ) : (
                          <>
                            <Button
                              type="button"
                              onClick={() => {
                                const slot = zone.schedule.windows[0];
                                setMode("zone");
                                setEditing(zone.id);
                                setEditingExclusion(null);
                                setName(zone.name);
                                setPoints(zone.polygon);
                                setClosed(true);
                                setDays(slot?.days ?? []);
                                setStart(slot?.start ?? "08:00");
                                setEnd(slot?.end ?? "18:00");
                                setRuleType(zone.rule_type);
                                setSeconds(String(zone.rule_params.seconds ?? 30));
                                setMaxPeople(String(zone.rule_params.max_people ?? 5));
                                setConfirming(null);
                              }}
                            >
                              Editar
                            </Button>
                            <Button type="button" onClick={() => setConfirming(zone.id)}>
                              Eliminar
                            </Button>
                          </>
                        )}
                      </div>
                    ) : null}
                  </article>
                ))}
                {exclusions.length === 0 ? <p className="page-tagline">Aún no hay exclusiones.</p> : null}
                {exclusions.map((area) => (
                  <article className="item" key={area.id}>
                    <h2 className="card-title">Exclusión</h2>
                    <p className="card-meta">{area.polygon.length} puntos · línea discontinua</p>
                    {admin ? (
                      <div className="actions">
                        {confirming === area.id ? (
                          <>
                            <span className="card-meta">¿Eliminar esta exclusión?</span>
                            <Button type="button" onClick={() => removeExclusion(area.id)} disabled={pending}>
                              Eliminar
                            </Button>
                            <Button type="button" onClick={() => setConfirming(null)}>
                              Cancelar
                            </Button>
                          </>
                        ) : (
                          <>
                            <Button
                              type="button"
                              onClick={() => {
                                setMode("exclusion");
                                setEditing(null);
                                setEditingExclusion(area.id);
                                setPoints(area.polygon);
                                setClosed(true);
                                setConfirming(null);
                              }}
                            >
                              Editar
                            </Button>
                            <Button type="button" onClick={() => setConfirming(area.id)}>
                              Eliminar
                            </Button>
                          </>
                        )}
                      </div>
                    ) : null}
                  </article>
                ))}
              </div>
            </div>
          </div>
        </div>
      </Frame>
    </>
  );
}
