import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { AppShell } from "@/components/app-shell";
import "./globals.css";

export const metadata: Metadata = {
  title: "DepthSnap — NFL Role Intelligence",
  description:
    "Documented NFL role changes, backfield control, and target hierarchy with raw evidence.",
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
