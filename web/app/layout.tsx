import type { Metadata } from "next";
import { ReactNode } from "react";

import { MotionPreference } from "@/lib/motion";

import "./globals.css";

export const metadata: Metadata = {
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
      <body>
        <MotionPreference />
        {children}
      </body>
    </html>
  );
}
