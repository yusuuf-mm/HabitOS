import type { ObjectiveShape as ShapeName } from "@/lib/objectivePalette";

interface ObjectiveShapeProps {
  shape: ShapeName;
  color: string;
  stroke?: string;
  size?: number;
  className?: string;
}

/**
 * A tiny SVG mark that can live inside another SVG (life map orbs) or stand
 * alone (calendar blocks and legend). Each objective has a different outline
 * so the palette is never the only way to tell objectives apart.
 */
export function ObjectiveShape({
  shape,
  color,
  stroke,
  size = 14,
  className,
}: ObjectiveShapeProps) {
  const common = { fill: color, stroke: stroke ?? "none", strokeWidth: stroke ? 1.4 : 0 };
  return (
    <svg
      viewBox="0 0 16 16"
      width={size}
      height={size}
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      {shape === "circle" && <circle cx="8" cy="8" r="5.7" {...common} />}
      {shape === "square" && <rect x="2.4" y="2.4" width="11.2" height="11.2" rx="1" {...common} />}
      {shape === "diamond" && <polygon points="8,1.8 14.2,8 8,14.2 1.8,8" {...common} />}
      {shape === "triangle" && <polygon points="8,1.9 14.4,13.6 1.6,13.6" {...common} />}
      {shape === "hexagon" && <polygon points="5,2 11,2 14.3,8 11,14 5,14 1.7,8" {...common} />}
      {shape === "ring" && (
        <>
          <circle cx="8" cy="8" r="5.9" fill="none" stroke={color} strokeWidth="2.8" />
          {stroke && <circle cx="8" cy="8" r="5.9" fill="none" stroke={stroke} strokeWidth="0.7" />}
        </>
      )}
      {shape === "cross" && (
        <polygon
          points="6.3,1.8 9.7,1.8 9.7,6.3 14.2,6.3 14.2,9.7 9.7,9.7 9.7,14.2 6.3,14.2 6.3,9.7 1.8,9.7 1.8,6.3 6.3,6.3"
          {...common}
        />
      )}
      {shape === "capsule" && <rect x="3" y="1.8" width="10" height="12.4" rx="5" {...common} />}
    </svg>
  );
}
