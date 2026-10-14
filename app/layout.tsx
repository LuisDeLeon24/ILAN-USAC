import type { Metadata } from "next";
import { ReactNode } from "react";

import "./globals.css";

const siteUrl = process.env.VERCEL_URL
  ? `https://${process.env.VERCEL_URL}`
  : "http://localhost:3000";

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  title: "Sentinel",
  description: "Detección de riesgos con inteligencia artificial",
  icons: { icon: "/brand/sentinel-favicon.png" },
  openGraph: {
    title: "Sentinel",
    description: "Detección de riesgos con inteligencia artificial",
    locale: "es_GT",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Sentinel",
    description: "Detección de riesgos con inteligencia artificial",
  },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
