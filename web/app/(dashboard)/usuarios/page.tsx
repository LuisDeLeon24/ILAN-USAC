"use client";

import { FormEvent, useEffect, useState } from "react";

import { Feedback, Field, Frame, PageHeader } from "@/components/frame";
import { useMe } from "@/components/shell";
import { Button } from "@/components/ui/button";
import { ApiError, api } from "@/lib/api";
import { ROLE_LABELS, formatWhen } from "@/lib/labels";
import type { Role, UserAccount } from "@/lib/types";

export default function UsersPage() {
  const me = useMe();
  const [rows, setRows] = useState<UserAccount[]>([]);
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<Role>("operator");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function load() {
    setRows(await api<UserAccount[]>("/users"));
  }

  useEffect(() => {
    if (!me || me.role !== "admin") {
      return;
    }
    load().catch((err: unknown) => setError(err instanceof Error ? err.message : "No se pudieron cargar los usuarios"));
  }, [me]);

  if (!me) {
    return null;
  }

  if (me.role !== "admin") {
    return (
      <>
        <PageHeader title="Usuarios" subtitle="Cuentas de la organización" tagline="Solo un administrador puede invitar personas." />
        <Frame>
          <p className="page-tagline">No tienes permiso para esta acción.</p>
        </Frame>
      </>
    );
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError("");
    try {
      await api("/users", {
        method: "POST",
        body: JSON.stringify({ full_name: fullName, email, password, role }),
      });
      setFullName("");
      setEmail("");
      setPassword("");
      setRole("operator");
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo crear el usuario");
    } finally {
      setPending(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Usuarios"
        subtitle="Cuentas de la organización"
        tagline="El administrador invita a cada persona. No hay registro público."
      />
      <Frame>
        <div className="stack">
          <form className="stack" onSubmit={onSubmit}>
            <Field label="Nombre">
              <input className="control" value={fullName} onChange={(event) => setFullName(event.target.value)} required />
            </Field>
            <Field label="Correo">
              <input className="control" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
            </Field>
            <Field label="Contraseña">
              <input
                className="control"
                type="password"
                autoComplete="new-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </Field>
            <Field label="Rol">
              <select className="control" value={role} onChange={(event) => setRole(event.target.value as Role)}>
                <option value="operator">Operador</option>
                <option value="admin">Administrador</option>
              </select>
            </Field>
            <Button type="submit" variant="primary" disabled={pending}>
              {pending ? "Guardando…" : "Invitar usuario"}
            </Button>
          </form>
          <Feedback message={error} />
          <div className="list">
            {rows.map((user) => (
              <article className="item" key={user.id}>
                <h2 className="card-title">{user.full_name}</h2>
                <p className="card-meta">
                  {user.email} · {ROLE_LABELS[user.role]}
                </p>
                <p className="card-meta">{formatWhen(user.created_at)}</p>
              </article>
            ))}
          </div>
        </div>
      </Frame>
    </>
  );
}
