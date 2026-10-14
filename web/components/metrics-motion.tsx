"use client";

import { useEffect, useState } from "react";
import { animated, useSpring, useTrail } from "@react-spring/web";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { spring } from "@/lib/motion";

type DayBar = {
  day: string;
  count: number;
};

type BarShape = {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  index?: number;
};

export function CountUp({ value, format }: { value: number; format: (value: number) => string }) {
  const shown = useSpring({
    from: { n: 0 },
    to: { n: value },
    config: spring,
  });
  return <animated.p className="metric-numeral">{shown.n.to((current) => format(current))}</animated.p>;
}

export function GrowingChart({ data }: { data: DayBar[] }) {
  const [play, setPlay] = useState(false);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => setPlay(true));
    return () => window.cancelAnimationFrame(frame);
  }, []);

  const [trail] = useTrail(
    data.length,
    {
      from: { scale: 0 },
      to: { scale: play ? 1 : 0 },
      config: spring,
    },
    [play],
  );

  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data}>
        <CartesianGrid stroke="var(--grid-color)" vertical={false} />
        <XAxis dataKey="day" tick={{ fill: "var(--sentinel-cream)" }} axisLine={{ stroke: "var(--line)" }} tickLine={false} />
        <YAxis allowDecimals={false} tick={{ fill: "var(--sentinel-cream)" }} axisLine={{ stroke: "var(--line)" }} tickLine={false} />
        <Tooltip
          cursor={{ fill: "var(--surface)" }}
          contentStyle={{
            background: "var(--sentinel-navy)",
            color: "var(--sentinel-cream)",
            border: "var(--border-width) solid var(--line)",
          }}
        />
        <Bar
          dataKey="count"
          fill="var(--sentinel-cream)"
          name="Eventos"
          isAnimationActive={false}
          shape={(props: unknown) => {
            const bar = props as BarShape;
            const x = bar.x ?? 0;
            const y = bar.y ?? 0;
            const width = bar.width ?? 0;
            const height = bar.height ?? 0;
            const scale = trail[bar.index ?? 0]?.scale;
            if (!scale) {
              return <rect x={x} y={y} width={width} height={0} fill="var(--sentinel-cream)" />;
            }
            return (
              <animated.rect
                x={x}
                width={width}
                y={scale.to((value) => y + height * (1 - value))}
                height={scale.to((value) => Math.max(0, height * value))}
                fill="var(--sentinel-cream)"
              />
            );
          }}
        />
      </BarChart>
    </ResponsiveContainer>
  );
}
