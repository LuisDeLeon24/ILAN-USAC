"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { Frame } from "@/components/frame";
import { api, apiBlob } from "@/lib/api";
import { countLabel, guatemalaDate, guatemalaDay } from "@/lib/labels";
import { consumePreview } from "@/lib/mjpeg";
import type { Camera } from "@/lib/types";

type LiveTicket = {
  token: string;
  stream_url: string;
  status_url: string;
};

type LiveStatus = {
  signal: boolean;
};

const TOKEN_REFRESH_MS = 4 * 60 * 1000;
const STATUS_POLL_MS = 1000;

function useOnScreen() {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const node = ref.current;
    if (!node) {
      return;
    }
    const observer = new IntersectionObserver(([entry]) => setVisible(entry.isIntersecting), { threshold: 0.25 });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return { ref, visible };
}

function useSnapshot(eventId: string | null) {
  const [url, setUrl] = useState("");

  useEffect(() => {
    if (!eventId) {
      setUrl("");
      return;
    }
    let active = true;
    let objectUrl = "";
    apiBlob(`/events/${eventId}/snapshot`)
      .then((value) => {
        objectUrl = value;
        if (active) {
          setUrl(value);
        } else {
          URL.revokeObjectURL(value);
        }
      })
      .catch(() => {
        if (active) {
          setUrl("");
        }
      });
    return () => {
      active = false;
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [eventId]);

  return url;
}

function useLivePreview(cameraId: string) {
  const [frameUrl, setFrameUrl] = useState("");
  const [signal, setSignal] = useState(false);

  useEffect(() => {
    if (!cameraId) {
      setFrameUrl("");
      setSignal(false);
      return;
    }
    let stopped = false;
    let objectUrl = "";
    let statusTimer = 0;
    const abort = { current: new AbortController() };

    const paint = (blob: Blob) => {
      if (stopped) {
        return;
      }
      const next = URL.createObjectURL(blob);
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
      objectUrl = next;
      setFrameUrl(next);
    };

    async function runTicket() {
      const ticket = await api<LiveTicket>(`/cameras/${cameraId}/live-token`, { method: "POST" });
      if (stopped) {
        return;
      }
      const token = encodeURIComponent(ticket.token);
      const statusUrl = `${ticket.status_url}?token=${token}`;
      const streamUrl = `${ticket.stream_url}?token=${token}`;
      const poll = () => {
        fetch(statusUrl, { signal: abort.current.signal, cache: "no-store" })
          .then(async (response) => {
            if (!response.ok) {
              throw new Error("sin señal");
            }
            return (await response.json()) as LiveStatus;
          })
          .then((body) => {
            if (!stopped) {
              setSignal(Boolean(body.signal));
            }
          })
          .catch(() => {
            if (!stopped && !abort.current.signal.aborted) {
              setSignal(false);
            }
          });
      };
      poll();
      statusTimer = window.setInterval(poll, STATUS_POLL_MS);
      await consumePreview(streamUrl, abort.current.signal, paint);
    }

    async function loop() {
      while (!stopped) {
        abort.current = new AbortController();
        const refreshTimer = window.setTimeout(() => abort.current.abort(), TOKEN_REFRESH_MS);
        let failed = false;
        try {
          await runTicket();
        } catch {
          failed = !stopped && !abort.current.signal.aborted;
          if (failed) {
            setSignal(false);
          }
        } finally {
          window.clearTimeout(refreshTimer);
          window.clearInterval(statusTimer);
        }
        if (stopped) {
          break;
        }
        if (failed || !abort.current.signal.aborted) {
          await new Promise((resolve) => window.setTimeout(resolve, STATUS_POLL_MS));
        }
      }
    }

    void loop();
    return () => {
      stopped = true;
      abort.current.abort();
      window.clearInterval(statusTimer);
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [cameraId]);

  return { frameUrl, signal };
}

export function cameraTodayCount(events: { camera_id: string | null; occurred_at: string }[], cameraId: string) {
  const today = guatemalaDate(0);
  return events.filter((event) => event.camera_id === cameraId && guatemalaDay(event.occurred_at) === today).length;
}

export function latestSnapshotId(events: { id: string; camera_id: string | null; has_snapshot: boolean }[], cameraId: string) {
  return events.find((event) => event.camera_id === cameraId && event.has_snapshot)?.id ?? null;
}

export function CameraCard({
  camera,
  siteName,
  todayCount,
  snapshotEventId,
}: {
  camera: Camera;
  siteName: string;
  todayCount: number;
  snapshotEventId: string | null;
}) {
  const { ref, visible } = useOnScreen();
  const live = useLivePreview(camera.enabled && visible ? camera.id : "");
  const snapshot = useSnapshot(camera.enabled ? null : snapshotEventId);
  const status = !camera.enabled ? "Inactiva" : live.signal ? "Analizando" : "Sin señal";
  const preview = camera.enabled ? live.frameUrl : snapshot;

  return (
    <Link className="camera-card" href={`/camaras/${camera.id}`}>
      <Frame>
        <div className="stack">
          <div className="camera-preview" ref={ref}>
            {preview ? (
              <img src={preview} alt={`Vista previa de ${camera.name}`} />
            ) : (
              <p className="camera-empty">Sin imagen</p>
            )}
          </div>
          <h2 className="card-title">{camera.name}</h2>
          <p className="card-meta">{siteName}</p>
          <p className="camera-status">{status}</p>
          <p className="card-meta">{countLabel(todayCount, "evento hoy", "eventos hoy")}</p>
        </div>
      </Frame>
    </Link>
  );
}
