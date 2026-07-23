"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ComponentType, SVGProps } from "react";
import {
  FeedIcon,
  PlayersIcon,
  ReportsIcon,
  SearchIcon,
  TeamsIcon,
} from "@/components/icons";

type NavigationItem = {
  href: string;
  label: string;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
};

const navigationItems: readonly NavigationItem[] = [
  { href: "/", label: "Feed", icon: FeedIcon },
  { href: "/reports", label: "Reports", icon: ReportsIcon },
  { href: "/teams", label: "Teams", icon: TeamsIcon },
  { href: "/players", label: "Players", icon: PlayersIcon },
];

function isCurrentPath(pathname: string, href: string) {
  return href === "/" ? pathname === href : pathname.startsWith(href);
}

export function DesktopNavigation() {
  const pathname = usePathname();

  return (
    <nav className="desktop-nav" aria-label="Primary navigation">
      {navigationItems.map(({ href, label }) => {
        const current = isCurrentPath(pathname, href);
        return (
          <Link href={href} key={href} aria-current={current ? "page" : undefined}>
            {label}
          </Link>
        );
      })}
    </nav>
  );
}

export function MobileNavigation() {
  const pathname = usePathname();
  const items = [
    ...navigationItems,
    { href: "/search", label: "Search", icon: SearchIcon },
  ];

  return (
    <nav className="mobile-nav" aria-label="Mobile navigation">
      {items.map(({ href, label, icon: Icon }) => {
        const current = isCurrentPath(pathname, href);
        return (
          <Link href={href} key={href} aria-current={current ? "page" : undefined}>
            <Icon />
            <span>{label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
