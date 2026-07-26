import { ImageResponse } from "next/og";

export const alt = "DepthSnap — NFL Role Intelligence";
export const size = {
  width: 1200,
  height: 630,
};
export const contentType = "image/png";

export default function OpenGraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          alignItems: "center",
          background:
            "radial-gradient(circle at 78% 18%, #14464b 0, #07171c 42%, #030a0d 100%)",
          color: "#f1fffd",
          display: "flex",
          height: "100%",
          justifyContent: "space-between",
          padding: "72px 84px",
          width: "100%",
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 26, width: 780 }}>
          <div
            style={{
              color: "#5de1cf",
              display: "flex",
              fontSize: 28,
              fontWeight: 700,
              letterSpacing: 5,
              textTransform: "uppercase",
            }}
          >
            NFL Role Intelligence
          </div>
          <div style={{ display: "flex", fontSize: 92, fontWeight: 800 }}>
            Depth<span style={{ color: "#5de1cf" }}>Snap</span>
          </div>
          <div
            style={{
              color: "#b9d8d4",
              display: "flex",
              fontSize: 38,
              lineHeight: 1.25,
            }}
          >
            Documented role changes with raw opportunities, denominators, and shares.
          </div>
        </div>
        <div
          style={{
            alignItems: "center",
            background: "#0c272c",
            border: "4px solid #5de1cf",
            borderRadius: 44,
            color: "#5de1cf",
            display: "flex",
            fontSize: 138,
            fontWeight: 900,
            height: 250,
            justifyContent: "center",
            width: 250,
          }}
        >
          D
        </div>
      </div>
    ),
    size,
  );
}
