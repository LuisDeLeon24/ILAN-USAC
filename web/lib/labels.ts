import type { Role } from "@/lib/types";

export const RULE_LABELS: Record<string, string> = {
  intrusion: "Intrusión",
  after_hours: "Fuera de horario",
  loitering: "Merodeo",
  occupancy: "Ocupación",
};

export const EVENT_LABELS: Record<string, string> = {
  ...RULE_LABELS,
  camera_disconnected: "Cámara desconectada",
  door_open: "Puerta abierta",
  motion: "Movimiento",
  smoke: "Humo",
  panic: "Botón de pánico",
};

export const SENSOR_TYPE_LABELS: Record<string, string> = {
  door: "Puerta",
  motion: "Movimiento",
  smoke: "Humo",
  panic: "Botón de pánico",
};

export const ALERT_STATUS_LABELS: Record<string, string> = {
  sent: "Enviada",
  failed: "Fallida",
  suppressed: "Suprimida",
};

export const ALERT_PROVIDER_LABELS: Record<string, string> = {
  console: "Consola",
  twilio: "Twilio",
  telegram: "Telegram",
};

export const ALERT_CHANNEL_LABELS: Record<string, string> = {
  whatsapp: "WhatsApp",
  telegram: "Telegram",
};

export const SEVERITY_LABELS: Record<string, string> = {
  low: "BAJA",
  medium: "MEDIA",
  high: "ALTA",
  critical: "CRÍTICO",
};

export const STATUS_LABELS: Record<string, string> = {
  new: "Nuevo",
  in_review: "En revisión",
  resolved: "Resuelto",
  false_positive: "Falso positivo",
};

export const STATUS_MARKS: Record<string, string> = {
  new: "●",
  in_review: "◐",
  resolved: "○",
  false_positive: "○",
};

export function scheduleCopy(ruleType: string): { title: string; days: string; help: string } {
  if (ruleType === "after_hours") {
    return {
      title: "Horario de operación permitido",
      days: "Días de operación",
      help: "La alerta se genera cuando hay una persona dentro de la zona fuera de este horario.",
    };
  }
  return {
    title: "Horario en que la regla está activa",
    days: "Días en que la regla está activa",
    help: "La regla solo se evalúa dentro de este horario. De 00:00 a 23:59, todos los días, queda activa las 24 horas.",
  };
}

export const ROLE_LABELS: Record<Role, string> = {
  admin: "Administrador",
  operator: "Operador",
};

export const DAY_OPTIONS = [
  ["mon", "Lun"],
  ["tue", "Mar"],
  ["wed", "Mié"],
  ["thu", "Jue"],
  ["fri", "Vie"],
  ["sat", "Sáb"],
  ["sun", "Dom"],
] as const;

export function guatemalaDay(value: string): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Guatemala",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date(value));
}

export function guatemalaDate(offsetDays = 0): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Guatemala",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
  const [year, month, day] = parts.split("-").map(Number);
  const utc = new Date(Date.UTC(year, month - 1, day));
  utc.setUTCDate(utc.getUTCDate() + offsetDays);
  return utc.toISOString().slice(0, 10);
}

export function formatWhen(value: string): string {
  return new Intl.DateTimeFormat("es-GT", {
    timeZone: "America/Guatemala",
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export function countLabel(count: number, singular: string, plural: string): string {
  return `${count} ${count === 1 ? singular : plural}`;
}
