"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, MouseEvent, ReactNode, useContext, useEffect, useState } from "react";

import { AlertToasts } from "@/components/alert-toasts";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { ROLE_LABELS } from "@/lib/labels";
import type { Me } from "@/lib/types";

const SessionContext = createContext<Me | null>(null);

export function useMe() {
  return useContext(SessionContext);
}

const LINKS = [
  { href: "/sitios", label: "Sitios" },
  { href: "/camaras", label: "Cámaras" },
  { href: "/sensores", label: "Sensores" },
  { href: "/eventos", label: "Eventos" },
  { href: "/metricas", label: "Métricas" },
  { href: "/asistente", label: "Senti" },
  { href: "/alertas", label: "Alertas", admin: true },
  { href: "/usuarios", label: "Usuarios", admin: true },
];

function isActive(href: string, pathname: string) {
  return pathname === href || pathname.startsWith(`${href}/`);
}

function sameLabel(left: string, right: string) {
  return left.trim().localeCompare(right.trim(), "es", { sensitivity: "base" }) === 0;
}

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [online, setOnline] = useState(false);

  useEffect(() => {
    const token = sessionStorage.getItem("sentinel_token");
    if (!token) {
      router.replace("/login");
      return;
    }
    api<Me>("/auth/me")
      .then(setMe)
      .catch(() => router.replace("/login"));
    const check = () => {
      fetch("/backend/health")
        .then((response) => setOnline(response.ok))
        .catch(() => setOnline(false));
    };
    check();
    const timer = window.setInterval(check, 30000);
    return () => window.clearInterval(timer);
  }, [router]);

  if (!me) {
    return (
      <div className="login-screen">
        <p className="page-subtitle">Cargando…</p>
      </div>
    );
  }

  function logout() {
    sessionStorage.removeItem("sentinel_token");
    router.replace("/login");
  }

  function follow(event: MouseEvent<HTMLAnchorElement>, href: string) {
    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
      return;
    }
    event.preventDefault();
    router.push(href);
  }

  return (
    <SessionContext.Provider value={me}>
      <div className="shell">
        <aside className="sidebar">
          <Link href="/sitios" className="wordmark-link" onClick={(event) => follow(event, "/sitios")}>
            <img className="wordmark" src="/brand/sentinel-wordmark-white.png" alt="Sentinel" />
          </Link>
          <nav>
            {LINKS.filter((link) => !link.admin || me.role === "admin").map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className={isActive(link.href, pathname) ? "nav-item active" : "nav-item"}
                onClick={(event) => follow(event, link.href)}
              >
                {link.label}
              </Link>
            ))}
          </nav>
          <div className="sidebar-foot">
            <p className="section-label">{me.organization_name}</p>
            <p className="card-meta">{me.full_name}</p>
            {sameLabel(me.full_name, ROLE_LABELS[me.role]) ? null : (
              <p className="card-meta">{ROLE_LABELS[me.role]}</p>
            )}
            <p className="status-line">
              <span className={online ? "status-dot status-online" : "status-dot"} aria-hidden="true">
                {online ? "●" : "○"}
              </span>
              {online ? "En línea" : "Sin conexión"}
            </p>
            <Button type="button" onClick={logout}>
              Cerrar sesión
            </Button>
          </div>
        </aside>
        <main className="canvas">
          <div className="canvas-inner">{children}</div>
        </main>
      </div>
      <AlertToasts />
    </SessionContext.Provider>
  );
}
