"use client";

import { useState } from "react";

type CopyState = "idle" | "copied" | "unavailable";

export function CopyHashButton({
  hash,
  bundleLabel,
}: {
  hash: string;
  bundleLabel: string;
}) {
  const [copyState, setCopyState] = useState<CopyState>("idle");

  async function copyHash() {
    try {
      await navigator.clipboard.writeText(hash);
      setCopyState("copied");
    } catch {
      setCopyState("unavailable");
    }
  }

  return (
    <div className="hash-copy-action">
      <button
        type="button"
        onClick={copyHash}
        aria-label={`Copy SHA-256 for ${bundleLabel}`}
      >
        Copy SHA-256
      </button>
      <span role="status" aria-live="polite">
        {copyState === "copied"
          ? "Copied SHA-256"
          : copyState === "unavailable"
            ? "Copy unavailable"
            : ""}
      </span>
    </div>
  );
}
