"use client";

import { FormEvent, useEffect, useState } from "react";

import { Feedback, Field, Frame, PageHeader } from "@/components/frame";
import { useMe } from "@/components/shell";
import { Button } from "@/components/ui/button";
import { ApiError, api } from "@/lib/api";
import { countLabel, formatWhen } from "@/lib/labels";
import type { Site } from "@/lib/types";

export default function SitesPage() {
  const me = useMe();
  const [rows, setRows] = useState<Site[]>([]);
  const [name, setName] = useState("");
  const [address, setAddress] = useState("");
  const [editing, setEditing] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [confirming, setConfirming] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function load() {
    setRows(await api<Site[]>("/sites"));
  }

  useEffect(() => {
    if (!me) {
      return;
    }
    load().catch((err: unknown) => setError(err instanceof Error ? err.message : "No se pudieron cargar los sitios"));
  }, [me]);

  if (!me) {
    return null;
  }

  function closeForm() {
    setName("");
    setAddress("");
    setEditing(null);
    setFormOpen(false);
  }

  function openCreate() {
    setEditing(null);
    setName("");
    setAddress("");
    setConfirming(null);
    setFormOpen(true);
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError("");
    const payload = { name, address: address.trim() || null };
    try {
      if (editing) {
        await api(`/sites/${editing}`, { method: "PATCH", body: JSON.stringify(payload) });
      } else {
        await api("/sites", { method: "POST", body: JSON.stringify(payload) });
      }
      closeForm();
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo guardar el sitio");
    } finally {
      setPending(false);
    }
  }

  async function remove(id: string) {
    setPending(true);
    setError("");
    try {
      await api(`/sites/${id}`, { method: "DELETE" });
      if (editing === id) {
        closeForm();
      }
      setConfirming(null);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo eliminar el sitio");
    } finally {
      setPending(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Sitios"
        subtitle="Ubicaciones bajo monitoreo"
        tagline="Agrupa las cámaras de cada instalación."
      />
      {me.role === "admin" && !formOpen ? (
        <div className="actions page-actions">
          <Button type="button" variant="primary" onClick={openCreate}>
            Agregar sitio
          </Button>
        </div>
      ) : null}
      {formOpen && me.role === "admin" ? (
        <Frame className="page-panel">
          <form className="stack" onSubmit={onSubmit}>
            <Field label="Nombre">
              <input className="control" value={name} onChange={(event) => setName(event.target.value)} required />
            </Field>
            <Field label="Dirección">
              <input
                className="control"
                value={address}
                placeholder="Ciudad de Guatemala"
                onChange={(event) => setAddress(event.target.value)}
              />
            </Field>
            <div className="actions">
              <Button type="submit" variant="primary" disabled={pending}>
                {pending ? "Guardando…" : editing ? "Guardar cambios" : "Guardar sitio"}
              </Button>
              <Button type="button" onClick={closeForm}>
                Cancelar
              </Button>
            </div>
          </form>
        </Frame>
      ) : null}
      <Feedback message={error} />
      <Frame>
        <div className="stack">
          {rows.length === 0 ? <p className="page-tagline">Aún no hay sitios.</p> : null}
          <div className="list">
            {rows.map((site) => (
              <article className="item" key={site.id}>
                <h2 className="card-title">{site.name}</h2>
                <p className="card-meta">{site.address || "Sin dirección"}</p>
                <p className="card-meta">
                  {countLabel(site.camera_count, "cámara", "cámaras")} · {formatWhen(site.created_at)}
                </p>
                {me.role === "admin" ? (
                  confirming === site.id ? (
                    <div className="actions">
                      <span className="card-meta">¿Eliminar este sitio?</span>
                      <Button type="button" onClick={() => remove(site.id)} disabled={pending}>
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
                          setEditing(site.id);
                          setName(site.name);
                          setAddress(site.address ?? "");
                          setConfirming(null);
                          setFormOpen(true);
                        }}
                      >
                        Editar
                      </Button>
                      <Button type="button" onClick={() => setConfirming(site.id)}>
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
