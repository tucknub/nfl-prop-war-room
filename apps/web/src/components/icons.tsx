import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

const iconProps = {
  width: 20,
  height: 20,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round",
  strokeLinejoin: "round",
  "aria-hidden": true,
} as const;

export function FeedIcon(props: IconProps) {
  return (
    <svg {...iconProps} {...props}>
      <path d="M4 5.5h16M4 12h11M4 18.5h8" />
      <path d="m17 15 3 3-3 3" />
    </svg>
  );
}

export function ReportsIcon(props: IconProps) {
  return (
    <svg {...iconProps} {...props}>
      <path d="M5 20V10M12 20V4M19 20v-7" />
    </svg>
  );
}

export function TeamsIcon(props: IconProps) {
  return (
    <svg {...iconProps} {...props}>
      <circle cx="9" cy="8" r="3" />
      <path d="M3.5 19c.5-3.1 2.3-5 5.5-5s5 1.9 5.5 5M15 6.2a3 3 0 0 1 0 5.6M16.5 14.2c2.3.5 3.7 2.1 4 4.8" />
    </svg>
  );
}

export function PlayersIcon(props: IconProps) {
  return (
    <svg {...iconProps} {...props}>
      <circle cx="12" cy="7.5" r="3.5" />
      <path d="M5.5 20c.6-4 2.8-6.2 6.5-6.2s5.9 2.2 6.5 6.2" />
    </svg>
  );
}

export function SearchIcon(props: IconProps) {
  return (
    <svg {...iconProps} {...props}>
      <circle cx="10.8" cy="10.8" r="6.3" />
      <path d="m16 16 4 4" />
    </svg>
  );
}

export function ArrowUpRightIcon(props: IconProps) {
  return (
    <svg {...iconProps} {...props}>
      <path d="M7 17 17 7M8 7h9v9" />
    </svg>
  );
}

export function ArrowRightIcon(props: IconProps) {
  return (
    <svg {...iconProps} {...props}>
      <path d="M5 12h14M14 7l5 5-5 5" />
    </svg>
  );
}

export function TrendUpIcon(props: IconProps) {
  return (
    <svg {...iconProps} {...props}>
      <path d="m5 16 5-5 3 3 6-7" />
      <path d="M14 7h5v5" />
    </svg>
  );
}

export function TrendDownIcon(props: IconProps) {
  return (
    <svg {...iconProps} {...props}>
      <path d="m5 8 5 5 3-3 6 7" />
      <path d="M14 17h5v-5" />
    </svg>
  );
}

export function MinusIcon(props: IconProps) {
  return (
    <svg {...iconProps} {...props}>
      <path d="M5 12h14" />
    </svg>
  );
}

export function StatusIcon(props: IconProps) {
  return (
    <svg {...iconProps} {...props}>
      <circle cx="12" cy="12" r="8" />
      <path d="M12 8v4l2.5 1.5" />
    </svg>
  );
}
