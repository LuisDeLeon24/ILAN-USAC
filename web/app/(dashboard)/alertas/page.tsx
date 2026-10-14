"use client";

import { FormEvent, useEffect, useState } from "react";

import { Feedback, Field, Frame, PageHeader } from "@/components/frame";
import { useMe } from "@/components/shell";
import { Button } from "@/components/ui/button";
import { ApiError, api } from "@/lib/api";
import { ALERT_CHANNEL_LABELS, ALERT_PROVIDER_LABELS, ALERT_STATUS_LABELS, EVENT_LABELS, formatWhen } from "@/lib/labels";
import type { AlertChannel, AlertContact, AlertLogItem, TelegramChat } from "@/lib/types";

const EMPTY_CHATS = "Nadie ha enviado /start al bot. Ábrelo en Telegram, envía /start y vuelve a intentar.";

export default function AlertsPage() {
  const me = useMe();
  const [contacts, setContacts] = useState<AlertContact[]>([]);
  const [logs, setLogs] = useState<AlertLogItem[]>([]);
  const [name, setName] = useState("");
  const [channel, setChannel] = useState<AlertChannel>("whatsapp");
  const [phone, setPhone] = useState("");
  const [chatId, setChatId] = useState<string | null>(null);
  const [chats, setChats] = useState<TelegramChat[]>([]);
  const [enabled, setEnabled] = useState(true);
  const [editing, setEditing] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [pending, setPending] = useState(false);
  const [linking, setLinking] = useState(false);

  async function load() {
    const [contactRows, logRows] = await Promise.all([
      api<AlertContact[]>("/alerts/contacts"),
      api<AlertLogItem[]>("/alerts/logs"),
    ]);
    setContacts(contactRows);
    setLogs(logRows);
  }

  useEffect(() => {
    if (!me || me.role !== "admin") {
      return;
    }
    load().catch((err: unknown) => setError(err instanceof Error ? err.message : "No se pudieron cargar las alertas"));
  }, [me]);

  if (!me) {
    return null;
  }

  if (me.role !== "admin") {
    return (
      <>
        <PageHeader
          title="Alertas"
          subtitle="Contactos de WhatsApp y Telegram"
          tagline="Solo un administrador gestiona los avisos."
        />
        <Frame>
          <p className="page-tagline">No tienes permiso para esta acción.</p>
        </Frame>
      </>
    );
  }

  function resetForm() {
    setName("");
    setChannel("whatsapp");
    setPhone("");
    setChatId(null);
    setChats([]);
    setEnabled(true);
    setEditing(null);
  }

  function contactBody(nextEnabled: boolean) {
    if (channel === "telegram") {
      return { name, channel, chat_id: chatId, enabled: nextEnabled };
    }
    return { name, channel, phone, enabled: nextEnabled };
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError("");
    setNotice("");
    if (channel === "telegram" && !chatId) {
      setError("Elige un chat de Telegram");
      setPending(false);
      return;
    }
    try {
      if (editing) {
        await api(`/alerts/contacts/${editing}`, { method: "PATCH", body: JSON.stringify(contactBody(enabled)) });
      } else {
        await api("/alerts/contacts", { method: "POST", body: JSON.stringify(contactBody(enabled)) });
      }
      resetForm();
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo guardar el contacto");
    } finally {
      setPending(false);
    }
  }

  async function linkTelegram() {
    setLinking(true);
    setError("");
    setNotice("");
    setChannel("telegram");
    try {
      const rows = await api<TelegramChat[]>("/alerts/telegram/chats");
      setChats(rows);
      if (rows.length === 0) {
        setNotice(EMPTY_CHATS);
      }
    } catch (err) {
      setChats([]);
      setError(err instanceof ApiError ? err.message : "No se pudieron leer los chats de Telegram");
    } finally {
      setLinking(false);
    }
  }

  function chooseChat(chat: TelegramChat) {
    setChatId(chat.chat_id);
    setChannel("telegram");
    setName((current) => (current.trim() ? current : chat.label));
    setNotice("");
  }

  async function remove(id: string) {
    setPending(true);
    setError("");
    try {
      await api(`/alerts/contacts/${id}`, { method: "DELETE" });
      if (editing === id) {
        resetForm();
      }
      setConfirming(null);
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo eliminar el contacto");
    } finally {
      setPending(false);
    }
  }

  async function toggle(contact: AlertContact) {
    setPending(true);
    setError("");
    const payload =
      contact.channel === "telegram"
        ? { name: contact.name, channel: "telegram", chat_id: contact.chat_id, enabled: !contact.enabled }
        : { name: contact.name, channel: "whatsapp", phone: contact.phone, enabled: !contact.enabled };
    try {
      await api(`/alerts/contacts/${contact.id}`, { method: "PATCH", body: JSON.stringify(payload) });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo actualizar el contacto");
    } finally {
      setPending(false);
    }
  }

  async function sendTest() {
    setPending(true);
    setError("");
    setNotice("");
    try {
      const result = await api<{ message: string }>("/alerts/test", { method: "POST" });
      if (result.message === "Alerta de prueba enviada") {
        setNotice(result.message);
      } else {
        setError(result.message);
      }
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo enviar la alerta de prueba");
    } finally {
      setPending(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Alertas"
        subtitle="Contactos de WhatsApp y Telegram"
        tagline="Se avisa desde severidad media. Pánico y humo siempre avisan. La prueba no crea un evento."
      />
      <Frame>
        <div className="stack">
          <p className="card-meta">
            Para Telegram, abre el bot y envía /start. Vincular Telegram muestra esos chats para elegir uno. La foto del
            evento se envía directo, sin una dirección pública.
          </p>
          <form className="stack" onSubmit={onSubmit}>
            <div className="field">
              <span className="section-label">Canal</span>
              <div className="actions">
                <button
                  type="button"
                  className={channel === "whatsapp" ? "chip on" : "chip"}
                  onClick={() => setChannel("whatsapp")}
                >
                  WhatsApp
                </button>
                <button
                  type="button"
                  className={channel === "telegram" ? "chip on" : "chip"}
                  onClick={() => setChannel("telegram")}
                >
                  Telegram
                </button>
              </div>
            </div>
            <Field label="Nombre">
              <input className="control" value={name} onChange={(event) => setName(event.target.value)} required />
            </Field>
            {channel === "whatsapp" ? (
              <Field label="WhatsApp">
                <input
                  className="control"
                  value={phone}
                  placeholder="+50255555555"
                  onChange={(event) => setPhone(event.target.value)}
                  required
                />
              </Field>
            ) : (
              <div className="stack">
                <div className="actions">
                  <Button type="button" onClick={linkTelegram} disabled={pending || linking}>
                    {linking ? "Buscando chats…" : "Vincular Telegram"}
                  </Button>
                </div>
                {chatId && chats.length === 0 ? (
                  <p className="card-meta">Telegram ya vinculado. Puedes buscar de nuevo para cambiar el chat.</p>
                ) : null}
                {chats.length > 0 ? (
                  <div className="list">
                    {chats.map((chat) => (
                      <article className="item" key={chat.chat_id}>
                        <h2 className="card-title">{chat.label}</h2>
                        {chat.username ? <p className="card-meta">@{chat.username}</p> : null}
                        <button
                          type="button"
                          className={chatId === chat.chat_id ? "chip on" : "chip"}
                          onClick={() => chooseChat(chat)}
                        >
                          {chatId === chat.chat_id ? "Elegido" : "Elegir"}
                        </button>
                      </article>
                    ))}
                  </div>
                ) : null}
              </div>
            )}
            <div className="field">
              <span className="section-label">Estado</span>
              <button type="button" className={enabled ? "chip on" : "chip"} onClick={() => setEnabled((value) => !value)}>
                {enabled ? "Activo" : "Inactivo"}
              </button>
            </div>
            <div className="actions">
              <Button type="submit" variant="primary" disabled={pending}>
                {pending ? "Guardando…" : editing ? "Guardar cambios" : "Guardar contacto"}
              </Button>
              {editing ? (
                <Button type="button" onClick={resetForm}>
                  Cancelar
                </Button>
              ) : null}
            </div>
          </form>
          <div className="actions">
            <Button type="button" onClick={sendTest} disabled={pending}>
              Enviar alerta de prueba
            </Button>
          </div>
          {notice ? <p className="page-tagline">{notice}</p> : null}
          <Feedback message={error} />
          {contacts.length === 0 ? <p className="page-tagline">Aún no hay contactos.</p> : null}
          <div className="list">
            {contacts.map((contact) => (
              <article className="item" key={contact.id}>
                <h2 className="card-title">{contact.name}</h2>
                <p className="section-label">{ALERT_CHANNEL_LABELS[contact.channel] ?? contact.channel}</p>
                {contact.channel === "whatsapp" && contact.phone ? <p className="card-meta">{contact.phone}</p> : null}
                <button
                  type="button"
                  className={contact.enabled ? "chip on" : "chip"}
                  onClick={() => toggle(contact)}
                  disabled={pending}
                >
                  {contact.enabled ? "Activo" : "Inactivo"}
                </button>
                {confirming === contact.id ? (
                  <div className="actions">
                    <span className="card-meta">¿Eliminar este contacto?</span>
                    <Button type="button" onClick={() => remove(contact.id)} disabled={pending}>
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
                        setEditing(contact.id);
                        setName(contact.name);
                        setChannel(contact.channel);
                        setPhone(contact.phone ?? "");
                        setChatId(contact.chat_id);
                        setChats([]);
                        setEnabled(contact.enabled);
                        setConfirming(null);
                      }}
                    >
                      Editar
                    </Button>
                    <Button type="button" onClick={() => setConfirming(contact.id)}>
                      Eliminar
                    </Button>
                  </div>
                )}
              </article>
            ))}
          </div>
          <p className="section-label">Intentos</p>
          {logs.length === 0 ? <p className="page-tagline">Aún no hay intentos.</p> : null}
          <div className="list">
            {logs.map((log) => (
              <article className="item" key={log.id}>
                <h2 className="card-title">{log.contact_name ?? "Sin contacto"}</h2>
                <p className="section-label">{ALERT_STATUS_LABELS[log.status] ?? log.status}</p>
                <p className="card-meta">
                  {ALERT_PROVIDER_LABELS[log.provider] ?? log.provider}
                  {log.is_test ? " · Prueba" : ""}
                  {log.event_type ? ` · ${EVENT_LABELS[log.event_type] ?? log.event_type}` : ""}
                  {" · "}
                  {formatWhen(log.created_at)}
                </p>
                {log.detail ? <p className="card-meta">{log.detail}</p> : null}
              </article>
            ))}
          </div>
        </div>
      </Frame>
    </>
  );
}
