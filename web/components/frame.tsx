import { ReactNode } from "react";

import { cn } from "@/lib/utils";

export function Frame({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <section className={cn("frame", className)}>
      <span className="mark mark-tl" aria-hidden="true">+</span>
      <span className="mark mark-tr" aria-hidden="true">+</span>
      <span className="mark mark-bl" aria-hidden="true">+</span>
      <span className="mark mark-br" aria-hidden="true">+</span>
      {children}
    </section>
  );
}

export function PageHeader({ title, subtitle, tagline }: { title: string; subtitle: string; tagline: string }) {
  return (
    <header className="page-header">
      <h1 className="page-title">{title}</h1>
      <p className="page-subtitle">{subtitle}</p>
      <p className="page-tagline">{tagline}</p>
    </header>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="field">
      <span className="section-label">{label}</span>
      {children}
    </label>
  );
}

export function Feedback({ message }: { message: string }) {
  if (!message) {
    return null;
  }
  return (
    <p className="form-error" role="alert">
      <span className="section-label">Error</span>
      {message}
    </p>
  );
}
