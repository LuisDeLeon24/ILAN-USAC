"use client";

import { useEffect } from "react";
import { Globals } from "@react-spring/web";

// friction / (2 * sqrt(mass * tension)) is just over 1, so the spring settles without overshoot.
export const spring = { mass: 1, tension: 170, friction: 27 };

// 8 / (2 * sqrt(8)) is about 1.4, so the aurora eases in and settles without a bounce.
export const auroraSpring = { mass: 1, tension: 8, friction: 8 };

function syncReducedMotion(): MediaQueryList | null {
  if (typeof window === "undefined") {
    return null;
  }
  const media = window.matchMedia("(prefers-reduced-motion: reduce)");
  Globals.assign({ skipAnimation: media.matches });
  return media;
}

if (typeof window !== "undefined") {
  syncReducedMotion();
}

export function slideFromTop(amount: number): string {
  return `translateY(calc(${amount} * var(--icon-tile-size) * -1))`;
}

export function slideFromCorner(x: number, y: number): string {
  return `translate(calc(${x} * var(--icon-tile-size)), calc(${y} * var(--icon-tile-size)))`;
}

export function MotionPreference() {
  useEffect(() => {
    const media = syncReducedMotion();
    if (!media) {
      return;
    }
    const onChange = () => {
      Globals.assign({ skipAnimation: media.matches });
    };
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);
  return null;
}
