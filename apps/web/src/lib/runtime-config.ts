import path from "node:path";
import type { LoaderFailure } from "@/lib/data-contract";

export type RuntimeDataConfiguration =
  | {
      ok: true;
      mode: "fixture" | "export" | undefined;
      dataRoot: string | undefined;
      allowFixtureDefault: boolean;
    }
  | {
      ok: false;
      failure: LoaderFailure;
    };

type RuntimeEnvironment = Record<string, string | undefined>;

function fail(message: string): RuntimeDataConfiguration {
  return {
    ok: false,
    failure: {
      category: "unsupported_data_mode",
      title: "Production data configuration unavailable",
      message,
      publicDetail:
        "The production data configuration is unavailable. No fallback data was used.",
    },
  };
}

export function resolveRuntimeDataConfiguration(
  environment: RuntimeEnvironment,
  cwd = process.cwd(),
): RuntimeDataConfiguration {
  const mode = environment.DEPTHSNAP_DATA_MODE;
  const dataRoot = environment.DEPTHSNAP_DATA_ROOT;
  const production = environment.NODE_ENV === "production";
  if (!production) {
    return {
      ok: true,
      mode: mode === "fixture" || mode === "export" ? mode : undefined,
      dataRoot,
      allowFixtureDefault: mode === undefined,
    };
  }

  const allowTestMode = environment.DEPTHSNAP_ALLOW_TEST_DATA_MODE === "1";
  if (mode !== "export" && !(allowTestMode && mode === "fixture")) {
    return fail("Production requires DEPTHSNAP_DATA_MODE=export.");
  }
  if (mode === "fixture") {
    return {
      ok: true,
      mode,
      dataRoot,
      allowFixtureDefault: false,
    };
  }
  if (!dataRoot) {
    return fail("Production export mode requires DEPTHSNAP_DATA_ROOT.");
  }
  const expectedRoot = path.resolve(cwd, "public", "data", "depthsnap");
  const suppliedRoot = path.resolve(cwd, dataRoot);
  if (
    suppliedRoot !== expectedRoot &&
    environment.DEPTHSNAP_ALLOW_TEST_DATA_ROOT !== "1"
  ) {
    return fail(
      "Production DEPTHSNAP_DATA_ROOT must resolve to public/data/depthsnap.",
    );
  }
  return {
    ok: true,
    mode: "export",
    dataRoot: suppliedRoot,
    allowFixtureDefault: false,
  };
}
