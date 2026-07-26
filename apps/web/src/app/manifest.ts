import type { MetadataRoute } from "next";

export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "DepthSnap — NFL Role Intelligence",
    short_name: "DepthSnap",
    description:
      "Documented NFL role changes with raw opportunities, denominators, and shares.",
    start_url: "/",
    display: "standalone",
    background_color: "#061014",
    theme_color: "#061014",
    icons: [
      {
        src: "/icon.svg",
        sizes: "any",
        type: "image/svg+xml",
      },
    ],
  };
}
