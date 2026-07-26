import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { AppShell } from "@/components/app-shell";
import "./globals.css";

const metadataBase = new URL(
  process.env.DEPTHSNAP_PUBLIC_ORIGIN ?? "http://127.0.0.1:3000",
);

export const metadata: Metadata = {
  metadataBase,
  applicationName: "DepthSnap",
  title: {
    default: "DepthSnap — NFL Role Intelligence",
    template: "%s — DepthSnap",
  },
  description:
    "Documented NFL role changes, backfield control, and target hierarchy with raw evidence.",
  keywords: [
    "NFL role intelligence",
    "backfield control",
    "target hierarchy",
    "role movement",
  ],
  robots: {
    index: true,
    follow: true,
  },
  openGraph: {
    type: "website",
    siteName: "DepthSnap",
    title: "DepthSnap — NFL Role Intelligence",
    description:
      "Documented NFL role changes with raw opportunities, denominators, shares, and publication status.",
  },
  twitter: {
    card: "summary_large_image",
    title: "DepthSnap — NFL Role Intelligence",
    description:
      "Documented NFL role changes with raw opportunities, denominators, shares, and publication status.",
  },
};

export const viewport: Viewport = {
  colorScheme: "dark",
  themeColor: "#061014",
};

export default function RootLayout({
  children,
}: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
