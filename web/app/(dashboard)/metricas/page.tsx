"use client";

import { FormEvent, useEffect, useState } from "react";

import { Feedback, Field, Frame, PageHeader } from "@/components/frame";
import { CountUp, GrowingChart } from "@/components/metrics-motion";
import { useMe } from "@/components/shell";
import { Button } from "@/components/ui/button";
import { ApiError, api } from "@/lib/api";
import type { Metrics } from "@/lib/types";

function monthTitle(monthStart: string): string {
  const [year, month] = monthStart.split("-").map(Number);
  return new Intl.DateTimeFormat("es-GT", { month: "long", year: "numeric", timeZone: "America/Guatemala" }).format(
    new Date(Date.UTC(year, month - 1, 1, 12)),
  );
}

function formatDuration(seconds: number): string {
  const total = Math.max(0, Math.round(seconds));
  const minutes = Math.floor(total / 60);
  const rest = total % 60;
  if (minutes === 0) {
    return `${rest} s`;
  }
  return `${minutes} min ${rest} s`;
}

function formatMoney(value: number, currency: string): string {
  return new Intl.NumberFormat("es-GT", { style: "currency", currency }).format(value);
}

function formatMinutes(value: number): string {
  return new Intl.NumberFormat("es-GT", { maximumFractionDigits: 2 }).format(value);
}

export default function MetricsPage() {
  const me = useMe();
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [rate, setRate] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [chartReady, setChartReady] = useState(false);

  async function load() {
    const data = await api<Metrics>("/metrics");
    setMetrics(data);
    setRate(String(data.rate_per_minute));
  }

  useEffect(() => {
    setChartReady(true);
  }, []);

  useEffect(() => {
    if (!me) {
      return;
    }
    load().catch((err: unknown) => setError(err instanceof Error ? err.message : "No se pudieron cargar las métricas"));
  }, [me]);

  if (!me || !metrics) {
    return error ? (
      <Frame>
        <Feedback message={error} />
      </Frame>
    ) : null;
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError("");
    try {
      await api("/pricing", { method: "PUT", body: JSON.stringify({ rate_per_minute: Number(rate) }) });
      await load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo guardar la tarifa");
    } finally {
      setPending(false);
    }
  }

  const chart = metrics.events_per_day.map((day) => ({
    day: String(Number(day.date.slice(8, 10))),
    count: day.count,
  }));

  return (
    <>
      <PageHeader
        title="Métricas"
        subtitle={monthTitle(metrics.month_start)}
        tagline="Eventos del mes, tiempo hasta revisión, minutos analizados y costo estimado con la tarifa de la organización."
      />
      <Frame>
        <div className="split">
          <div>
            <p className="section-label">Eventos por día</p>
            <div className="chart-panel">
              {chartReady ? <GrowingChart data={chart} /> : null}
            </div>
          </div>
          <div className="stack">
            <div>
              {metrics.average_response_seconds === null ? (
                <p className="page-subtitle">Sin datos</p>
              ) : (
                <CountUp value={metrics.average_response_seconds} format={formatDuration} />
              )}
              <p className="metric-label">Tiempo de respuesta</p>
            </div>
            <div>
              <CountUp value={metrics.analyzed_minutes} format={formatMinutes} />
              <p className="metric-label">Minutos analizados</p>
            </div>
            <div>
              <CountUp value={metrics.estimated_cost} format={(value) => formatMoney(value, metrics.currency)} />
              <p className="metric-label">Costo estimado</p>
            </div>
            {me.role === "admin" ? (
              <form className="stack" onSubmit={onSubmit}>
                <Field label="Tarifa por minuto (GTQ)">
                  <input
                    className="control"
                    type="number"
                    min="0"
                    step="0.0001"
                    value={rate}
                    onChange={(event) => setRate(event.target.value)}
                    required
                  />
                </Field>
                <Button type="submit" variant="primary" disabled={pending}>
                  {pending ? "Guardando…" : "Guardar tarifa"}
                </Button>
              </form>
            ) : (
              <p className="card-meta">Tarifa por minuto: {formatMoney(metrics.rate_per_minute, metrics.currency)}</p>
            )}
            {metrics.previous_month_start ? (
              <p className="card-meta">
                Referencia de {monthTitle(metrics.previous_month_start)}:{" "}
                {formatMinutes(metrics.previous_analyzed_minutes ?? 0)} minutos,{" "}
                {formatMoney(metrics.previous_estimated_cost ?? 0, metrics.currency)}. El mes en curso cuenta solo hasta hoy.
              </p>
            ) : null}
            <Feedback message={error} />
          </div>
        </div>
      </Frame>
    </>
  );
}
