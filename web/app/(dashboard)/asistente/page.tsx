"use client";

import { useEffect, useRef, useState } from "react";

import { Feedback, Frame, PageHeader } from "@/components/frame";
import { SentiComposer } from "@/components/senti-composer";
import { useMe } from "@/components/shell";
import { Button } from "@/components/ui/button";
import { ApiError, api } from "@/lib/api";
import type { AgentThread, Site } from "@/lib/types";

const GREETING = "Hola, soy Senti. Pregúntame qué pasó en tus sitios.";

export default function AssistantPage() {
  const me = useMe();
  const threadRef = useRef<HTMLDivElement>(null);
  const [thread, setThread] = useState<AgentThread>({ messages: [], confirmation: null });
  const [sites, setSites] = useState<Site[]>([]);
  const [siteId, setSiteId] = useState("");
  const [content, setContent] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight });
  }, [thread, pending]);

  useEffect(() => {
    if (!me) {
      return;
    }
    api<AgentThread>("/agent/messages")
      .then(setThread)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "No se pudo abrir Senti"));
    api<Site[]>("/sites")
      .then((rows) => setSites([...rows].sort((left, right) => left.name.localeCompare(right.name, "es"))))
      .catch(() => setSites([]));
  }, [me]);

  if (!me) {
    return null;
  }

  async function send(text: string) {
    const question = text.trim();
    if (!question || pending) {
      return;
    }
    setPending(true);
    setError("");
    try {
      const next = await api<AgentThread>("/agent/messages", {
        method: "POST",
        body: JSON.stringify(siteId ? { content: question, site_id: siteId } : { content: question }),
      });
      setThread(next);
      setContent("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo enviar la pregunta");
    } finally {
      setPending(false);
    }
  }

  async function decide(path: "/agent/confirm" | "/agent/cancel") {
    if (!thread.confirmation || pending) {
      return;
    }
    setPending(true);
    setError("");
    try {
      const next = await api<AgentThread>(path, {
        method: "POST",
        body: JSON.stringify({ id: thread.confirmation.id }),
      });
      setThread(next);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo confirmar la acción");
    } finally {
      setPending(false);
    }
  }

  async function startFresh() {
    if (pending) {
      return;
    }
    setPending(true);
    setError("");
    try {
      const next = await api<AgentThread>("/agent/reset", { method: "POST" });
      setThread(next);
      setContent("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo iniciar la conversación");
    } finally {
      setPending(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Senti"
        subtitle="Tu asistente de seguridad"
        tagline="Pregunta por eventos, minutos analizados y el estado del equipo. Un cambio de estado se aplica solo después de confirmarlo."
      />
      <Frame className="chat-frame">
        <div className="chat-thread" ref={threadRef}>
          {thread.messages.length === 0 ? (
            <article className="chat-message senti-message">
              <img className="senti-avatar" src="/brand/sentinel-icon.png" alt="" />
              <div>
                <p className="section-label">Senti</p>
                <p className="chat-copy">{GREETING}</p>
              </div>
            </article>
          ) : (
            thread.messages.map((message) =>
              message.role === "user" ? (
                <article className="chat-message chat-user" key={message.id}>
                  <p className="section-label">Tú</p>
                  <p className="chat-copy">{message.content}</p>
                </article>
              ) : (
                <article className="chat-message senti-message" key={message.id}>
                  <img className="senti-avatar" src="/brand/sentinel-icon.png" alt="" />
                  <div>
                    <p className="section-label">Senti</p>
                    <p className="chat-copy">{message.content}</p>
                  </div>
                </article>
              ),
            )
          )}
          {pending ? (
            <article className="chat-message senti-message" aria-live="polite">
              <img className="senti-avatar" src="/brand/sentinel-icon.png" alt="" />
              <div>
                <p className="section-label">Senti</p>
                <p className="chat-copy">Pensando…</p>
              </div>
            </article>
          ) : null}
        </div>
        <div className="chat-dock">
          {thread.confirmation ? (
            <div className="actions">
              <Button type="button" variant="primary" disabled={pending} onClick={() => void decide("/agent/confirm")}>
                Confirmar
              </Button>
              <Button type="button" disabled={pending} onClick={() => void decide("/agent/cancel")}>
                Cancelar
              </Button>
            </div>
          ) : null}
          <SentiComposer
            value={content}
            onChange={setContent}
            onSubmit={(text) => void send(text)}
            onReset={() => void startFresh()}
            pending={pending}
            sites={sites}
            siteId={siteId}
            onSite={setSiteId}
            emphasis={!thread.confirmation}
            onNotice={setError}
          />
          <Feedback message={error} />
        </div>
      </Frame>
    </>
  );
}
