"use client";

import { MouseEvent, PointerEvent, useRef } from "react";

import type { Exclusion, Zone } from "@/lib/types";

const CLOSE_DISTANCE = 14;

type Point = [number, number];

function asPoint(point: number[]): Point {
  return [point[0] ?? 0, point[1] ?? 0];
}

function pathOf(points: number[][]): string {
  return points.map((point) => `${point[0]},${point[1]}`).join(" ");
}

function roundCoord(value: number): number {
  return Math.round(Math.min(1, Math.max(0, value)) * 10000) / 10000;
}

export function PolygonEditor({
  imageUrl,
  zones,
  exclusions,
  points,
  closed,
  mode,
  editable,
  onChange,
}: {
  imageUrl: string;
  zones: Zone[];
  exclusions: Exclusion[];
  points: number[][];
  closed: boolean;
  mode: "zone" | "exclusion";
  editable: boolean;
  onChange: (points: number[][], closed: boolean) => void;
}) {
  const svgRef = useRef<SVGSVGElement>(null);
  const dragIndex = useRef<number | null>(null);
  const dragged = useRef(false);

  function locate(event: { clientX: number; clientY: number }): Point {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect || rect.width === 0 || rect.height === 0) {
      return [0, 0];
    }
    return [roundCoord((event.clientX - rect.left) / rect.width), roundCoord((event.clientY - rect.top) / rect.height)];
  }

  function near(event: { clientX: number; clientY: number }, point: number[]): boolean {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) {
      return false;
    }
    const dx = event.clientX - rect.left - point[0] * rect.width;
    const dy = event.clientY - rect.top - point[1] * rect.height;
    return Math.hypot(dx, dy) <= CLOSE_DISTANCE;
  }

  function onPointerMove(event: PointerEvent<SVGSVGElement>) {
    if (dragIndex.current === null) {
      return;
    }
    dragged.current = true;
    const next = points.map((point, index) => (index === dragIndex.current ? locate(event) : asPoint(point)));
    onChange(next, closed);
  }

  function onPointerUp() {
    dragIndex.current = null;
  }

  function onCanvasClick(event: MouseEvent<SVGSVGElement>) {
    if (!editable || closed || dragIndex.current !== null) {
      return;
    }
    if (dragged.current) {
      dragged.current = false;
      return;
    }
    const target = event.target as Element;
    if (target.classList.contains("vertex")) {
      return;
    }
    if (points.length >= 3 && near(event, points[0])) {
      onChange(points, true);
      return;
    }
    onChange([...points, locate(event)], false);
  }

  const draftClass = mode === "exclusion" ? "exclusion-line" : "zone-line";

  return (
    <div className="stage">
      {imageUrl ? (
        <img className="stage-image" src={imageUrl} alt="Cuadro de la cámara" />
      ) : (
        <p className="page-tagline stage-empty">Aún no hay un cuadro de esta cámara.</p>
      )}
      <svg
        ref={svgRef}
        className={editable ? "stage-draw editable" : "stage-draw"}
        viewBox="0 0 1 1"
        preserveAspectRatio="none"
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onClick={onCanvasClick}
      >
        {zones.map((zone) => (
          <polygon key={zone.id} className="zone-line" points={pathOf(zone.polygon)} />
        ))}
        {exclusions.map((area) => (
          <polygon key={area.id} className="exclusion-line" points={pathOf(area.polygon)} />
        ))}
        {points.length >= 2 ? (
          closed ? (
            <polygon className={draftClass} points={pathOf(points)} />
          ) : (
            <polyline className={draftClass} fill="none" points={pathOf(points)} />
          )
        ) : null}
        {editable
          ? points.map((point, index) => (
              <circle
                key={index}
                className="vertex"
                cx={point[0]}
                cy={point[1]}
                r={0.012}
                onPointerDown={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  dragIndex.current = index;
                  dragged.current = false;
                  svgRef.current?.setPointerCapture(event.pointerId);
                }}
                onClick={(event) => event.stopPropagation()}
              />
            ))
          : null}
      </svg>
    </div>
  );
}
