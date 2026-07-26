import "server-only";

import type {
  BackfieldReportBundle,
  HomeBundle,
  LoaderFailure,
  Manifest,
  MovementReportBundle,
  PlayerBundle,
  PlayersIndexBundle,
  ReportsIndexBundle,
  SearchBundle,
  StatusBundle,
  TargetReportBundle,
  TeamBundle,
  TeamsIndexBundle,
} from "@/lib/data-contract";
import {
  getRegistryBundle,
  type DepthSnapRegistry,
  type PublicationVariant,
} from "@/lib/data-registry-core";
import { loadCachedDepthSnapRegistry } from "@/lib/data-registry-cache";
import type { ReportFamily } from "@/lib/types";

export type LoadedData<T> = {
  ok: true;
  data: T;
  manifest: Manifest;
};

export type FailedData = {
  ok: false;
  failure: LoaderFailure;
};

export type DataLoadResult<T> = LoadedData<T> | FailedData;

export function publicationVariantFromState(
  state: string | undefined,
): PublicationVariant {
  if (state === "empty" || state === "unpublished")
    return "no_published_week";
  if (state === "unavailable") return "unavailable";
  return "published";
}

async function registryForState(
  state?: string,
): Promise<
  | { ok: true; registry: DepthSnapRegistry }
  | { ok: false; failure: LoaderFailure }
> {
  const mode = process.env.DEPTHSNAP_DATA_MODE;
  return loadCachedDepthSnapRegistry({
    mode,
    dataRoot: process.env.DEPTHSNAP_DATA_ROOT,
    publicationVariant: publicationVariantFromState(state),
    allowFixtureDefault:
      mode === undefined && process.env.NODE_ENV === "development",
  });
}

async function loadBundle<T>(
  family:
    | "home"
    | "reports_index"
    | "report_backfield"
    | "report_targets"
    | "report_movement"
    | "teams_index"
    | "team"
    | "players_index"
    | "player"
    | "search"
    | "status",
  state?: string,
  id?: string,
): Promise<DataLoadResult<T | null>> {
  const result = await registryForState(state);
  if (!result.ok) return result;
  const bundle = getRegistryBundle(result.registry, family, id);
  return {
    ok: true,
    data: (bundle as T | undefined) ?? null,
    manifest: result.registry.manifest,
  };
}

function required<T>(
  result: DataLoadResult<T | null>,
  familyLabel: string,
): DataLoadResult<T> {
  if (!result.ok) return result;
  if (result.data) {
    return { ok: true, data: result.data, manifest: result.manifest };
  }
  return {
    ok: false,
    failure: {
      category: "bundle_missing",
      title: "Required bundle unavailable",
      message: `${familyLabel} is not present in the selected manifest.`,
      publicDetail: "A required data bundle is unavailable.",
    },
  };
}

export async function loadHomeData(
  state?: string,
): Promise<DataLoadResult<HomeBundle>> {
  return required(await loadBundle<HomeBundle>("home", state), "Home");
}

export async function loadReportsIndexData(
  state?: string,
): Promise<DataLoadResult<ReportsIndexBundle>> {
  return required(
    await loadBundle<ReportsIndexBundle>("reports_index", state),
    "Reports index",
  );
}

export async function loadReportData(
  family: ReportFamily,
  state?: string,
): Promise<
  DataLoadResult<
    BackfieldReportBundle | TargetReportBundle | MovementReportBundle
  >
> {
  const bundleFamily =
    family === "backfield_control"
      ? "report_backfield"
      : family === "target_hierarchy"
        ? "report_targets"
        : "report_movement";
  return required(
    await loadBundle<
      BackfieldReportBundle | TargetReportBundle | MovementReportBundle
    >(bundleFamily, state),
    "Report",
  );
}

export async function loadTeamsIndexData(
  state?: string,
): Promise<DataLoadResult<TeamsIndexBundle>> {
  return required(
    await loadBundle<TeamsIndexBundle>("teams_index", state),
    "Teams index",
  );
}

export async function loadTeamData(
  teamId: string,
  state?: string,
): Promise<DataLoadResult<TeamBundle | null>> {
  return loadBundle<TeamBundle>("team", state, teamId.toUpperCase());
}

export async function loadPlayersIndexData(
  state?: string,
): Promise<DataLoadResult<PlayersIndexBundle>> {
  return required(
    await loadBundle<PlayersIndexBundle>("players_index", state),
    "Players index",
  );
}

export async function loadPlayerData(
  playerId: string,
  state?: string,
): Promise<DataLoadResult<PlayerBundle | null>> {
  return loadBundle<PlayerBundle>("player", state, playerId.toLowerCase());
}

export async function loadSearchData(
  state?: string,
): Promise<DataLoadResult<SearchBundle>> {
  return required(
    await loadBundle<SearchBundle>("search", state),
    "Search index",
  );
}

export async function loadStatusData(
  state?: string,
): Promise<DataLoadResult<StatusBundle>> {
  return required(
    await loadBundle<StatusBundle>("status", state),
    "Data status",
  );
}
