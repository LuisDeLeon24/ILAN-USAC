"use client";

import { ReactNode } from "react";
import { animated, useTransition } from "@react-spring/web";

import { slideFromTop, spring } from "@/lib/motion";

type MotionItem = { id: string };

export function EventMotion<T extends MotionItem>({
  items,
  layout,
  className,
  activeId,
  children,
}: {
  items: T[];
  layout: "stack" | "row";
  className: string;
  activeId?: string;
  children: (item: T) => ReactNode;
}) {
  const transitions = useTransition(items, {
    keys: (item) => item.id,
    from: { opacity: 0, span: 0, y: 1 },
    enter: { opacity: 1, span: 1, y: 0 },
    leave: { opacity: 0, span: 0, y: 0 },
    initial: { opacity: 1, span: 1, y: 0 },
    config: spring,
  });

  return (
    <div className={className}>
      {transitions((style, item) => {
        const open = activeId === item.id;
        const motionClass = layout === "row" ? "event-motion event-motion-row" : "event-motion";
        return (
          <animated.div
            className={open ? `${motionClass} is-open` : motionClass}
            style={{
              opacity: style.opacity,
              overflow: "hidden",
              transform: style.y.to(slideFromTop),
              ...(layout === "stack"
                ? { display: "grid", gridTemplateRows: style.span.to((value: number) => `${value}fr`) }
                : {
                    width: style.span.to(
                      (value: number) => `min(calc(${value} * var(--icon-tile-size) * 5), 100%)`,
                    ),
                  }),
            }}
          >
            <div className="event-motion-clip">{children(item)}</div>
          </animated.div>
        );
      })}
    </div>
  );
}
