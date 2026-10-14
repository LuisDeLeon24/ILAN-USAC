"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { Feedback, Field, Frame } from "@/components/frame";
import { Button } from "@/components/ui/button";
import { ApiError, api } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (sessionStorage.getItem("sentinel_token")) {
      router.replace("/sitios");
    }
  }, [router]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError("");
    try {
      const result = await api<{ access_token: string }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      sessionStorage.setItem("sentinel_token", result.access_token);
      router.replace("/sitios");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo iniciar sesión");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="login-screen">
      <Frame className="login-panel">
        <div className="stack">
          <img className="login-wordmark" src="/brand/sentinel-wordmark-white.png" alt="Sentinel" />
          <header className="login-heading">
            <h1 className="page-title">Iniciar sesión</h1>
            <p className="page-subtitle">Acceso al centro de monitoreo</p>
            <p className="page-tagline">Ingresa con la cuenta de tu organización.</p>
          </header>
          <form className="stack" onSubmit={onSubmit}>
            <Field label="Correo">
              <input
                className="control"
                type="email"
                autoComplete="username"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
            </Field>
            <Field label="Contraseña">
              <input
                className="control"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </Field>
            <Feedback message={error} />
            <Button type="submit" variant="primary" disabled={pending}>
              {pending ? "Entrando…" : "Entrar"}
            </Button>
          </form>
        </div>
      </Frame>
    </div>
  );
}
