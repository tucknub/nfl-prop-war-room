import { z } from "zod";

export const SHARE_TOLERANCE = 0.0005;

export const DataModeSchema = z.enum(["fixture", "export"]);
export const PublicationStatusSchema = z.enum([
  "published",
  "no_published_week",
  "unavailable",
]);
export const PublicationValidationResultSchema = z.enum([
  "pass",
  "fail",
  "not_applicable",
]);
export const ProductIdSchema = z.literal("depthsnap");
export const DataQualitySchema = z.enum([
  "complete",
  "reviewed_partial_game",
  "unavailable_supporting_context",
]);
export const ReportFamilySchema = z.enum([
  "backfield_control",
  "target_hierarchy",
  "role_movement",
]);
export const PlayerPositionSchema = z.enum(["RB", "WR", "TE"]);
export const OpportunityLabelSchema = z.enum([
  "opportunities",
  "carries",
  "targets",
]);
export const MovementDirectionSchema = z.enum(["gain", "decline", "stable"]);
export const VisualAccentSchema = z.enum(["teal", "amber", "slate"]);

const StableIdSchema = z.string().min(1).max(96);
const HrefSchema = z.string().startsWith("/");
const TimestampSchema = z.string().datetime({ offset: true });

export const RawShareEvidenceSchema = z
  .object({
    numerator: z.number().int().nonnegative(),
    denominator: z.number().int().positive(),
    share: z.number().min(0).max(1),
    opportunityLabel: OpportunityLabelSchema,
  })
  .strict()
  .superRefine((value, context) => {
    if (value.numerator > value.denominator) {
      context.addIssue({
        code: "custom",
        path: ["numerator"],
        message: "numerator must not exceed denominator",
      });
    }
    const expected = value.numerator / value.denominator;
    if (Math.abs(value.share - expected) > SHARE_TOLERANCE) {
      context.addIssue({
        code: "custom",
        path: ["share"],
        message: `share must match numerator / denominator within ${SHARE_TOLERANCE}`,
      });
    }
  });

export const MovementEvidenceSchema = z
  .object({
    previous: RawShareEvidenceSchema,
    current: RawShareEvidenceSchema,
    percentagePointChange: z.number(),
  })
  .strict()
  .superRefine((value, context) => {
    const expected = (value.current.share - value.previous.share) * 100;
    if (Math.abs(value.percentagePointChange - expected) > 0.05) {
      context.addIssue({
        code: "custom",
        path: ["percentagePointChange"],
        message: "percentage-point change must match current minus previous share",
      });
    }
  });

export const TeamIdentitySchema = z
  .object({
    id: StableIdSchema,
    abbreviation: z.string().min(2).max(8),
    name: z.string().min(1),
    conference: z.string().min(1).optional(),
    division: z.string().min(1).optional(),
    monogram: z.string().min(1).max(8),
    accent: VisualAccentSchema,
    href: HrefSchema,
    searchAliases: z.array(z.string().min(1)),
  })
  .strict();

export const PlayerIdentitySchema = z
  .object({
    id: StableIdSchema,
    name: z.string().min(1),
    team: z.string().min(1),
    teamId: StableIdSchema,
    position: PlayerPositionSchema,
    href: HrefSchema,
    jerseyNumber: z.number().int().positive().max(99).optional(),
    searchAliases: z.array(z.string().min(1)),
  })
  .strict();

export const ReportPeriodSchema = z
  .object({
    label: z.string().min(1),
    startWeek: z.number().int().min(1).max(18),
    endWeek: z.number().int().min(1).max(18),
  })
  .strict()
  .refine((period) => period.startWeek <= period.endWeek, {
    message: "startWeek must not exceed endWeek",
  });

export const ReportViewOptionSchema = z
  .object({
    id: StableIdSchema,
    label: z.string().min(1),
    description: z.string().min(1),
    currentPeriod: ReportPeriodSchema,
    priorPeriod: ReportPeriodSchema.optional(),
  })
  .strict();

export const ReportSortSchema = z.enum([
  "authority",
  "share",
  "gainers",
  "decliners",
  "absolute_change",
  "player",
  "team",
]);

export const SupportingContextSchema = z
  .object({
    label: z.string().min(1),
    evidence: RawShareEvidenceSchema,
  })
  .strict();

export const ReportSummarySchema = z
  .object({
    answer: z.string().min(1),
    items: z.array(
      z
        .object({
          label: z.string().min(1),
          value: z.string().min(1),
          detail: z.string().min(1),
        })
        .strict(),
    ),
  })
  .strict();

export const CurrentEvidenceRowSchema = z
  .object({
    id: StableIdSchema,
    authoritativeRank: z.number().int().positive(),
    player: PlayerIdentitySchema,
    roleFamily: z.string().min(1),
    current: RawShareEvidenceSchema,
    supportingContext: SupportingContextSchema.optional(),
    classificationLabel: z.string().min(1),
    teamHref: HrefSchema,
    playerHref: HrefSchema,
    evidenceHref: HrefSchema,
    dataQuality: DataQualitySchema,
  })
  .strict();

export const MovementEvidenceRowSchema = z
  .object({
    id: StableIdSchema,
    authoritativeRank: z.number().int().positive(),
    player: PlayerIdentitySchema,
    roleFamily: z.string().min(1),
    movement: MovementEvidenceSchema,
    direction: MovementDirectionSchema,
    movementLabel: z.string().min(1),
    finding: z.string().min(1),
    supportingContext: SupportingContextSchema.optional(),
    teamHref: HrefSchema,
    playerHref: HrefSchema,
    evidenceHref: HrefSchema,
    dataQuality: DataQualitySchema,
  })
  .strict();

export const ReportLinkSchema = z
  .object({
    family: ReportFamilySchema,
    label: z.string().min(1),
    description: z.string().min(1),
    href: HrefSchema,
  })
  .strict();

export const FeedFindingSchema = z
  .object({
    id: StableIdSchema,
    kind: z.enum([
      "backfield_increase",
      "target_share_increase",
      "role_decline",
      "concentrated_role",
      "committee_formation",
    ]),
    reportFamily: ReportFamilySchema,
    roleFamily: z.string().min(1),
    player: PlayerIdentitySchema,
    headline: z.string().min(1),
    current: RawShareEvidenceSchema,
    movement: MovementEvidenceSchema.optional(),
    evidenceHref: HrefSchema,
  })
  .strict();

export const TeamSnapshotSchema = z
  .object({
    monogram: z.string().min(1),
    teamName: z.string().min(1),
    teamCode: StableIdSchema,
    week: z.number().int().min(1).max(18),
    rows: z.array(
      z
        .object({
          role: z.enum(["RB1", "RB2", "WR1", "TE1"]),
          player: z.string().min(1),
          evidence: RawShareEvidenceSchema,
          tone: z.enum(["lead", "secondary"]),
        })
        .strict(),
    ),
    biggestMovement: z
      .object({
        player: z.string().min(1),
        summary: z.string().min(1),
        percentagePointChange: z.number(),
        evidenceHref: HrefSchema,
      })
      .strict(),
    reportHref: HrefSchema,
  })
  .strict();

export const LeaderboardRowSchema = z
  .object({
    rank: z.number().int().positive(),
    player: PlayerIdentitySchema,
    evidence: RawShareEvidenceSchema,
    movementPoints: z.number(),
    evidenceHref: HrefSchema,
  })
  .strict();

export const ReportLeaderboardSchema = z
  .object({
    backfield_control: z.array(LeaderboardRowSchema),
    target_hierarchy: z.array(LeaderboardRowSchema),
    role_movement: z.array(LeaderboardRowSchema),
  })
  .strict();

const BundleBaseShape = {
  dataMode: DataModeSchema,
  dataNotice: z.string().min(1),
  status: PublicationStatusSchema,
  season: z.number().int().min(2000).max(2200),
  throughWeek: z.number().int().min(1).max(18).nullable(),
  generatedAt: TimestampSchema,
  sourceVersion: z.string().min(1),
};

const StateMessageShape = {
  stateTitle: z.string().min(1),
  stateMessage: z.string().min(1),
};

const HomeBaseShape = {
  ...BundleBaseShape,
  schemaVersion: z.literal("depthsnap.home.v1"),
  reportLinks: z.array(ReportLinkSchema),
};
export const HomeBundleSchema = z.discriminatedUnion("status", [
  z
    .object({
      ...HomeBaseShape,
      status: z.literal("published"),
      throughWeek: z.number().int().min(1).max(18),
      leadFinding: FeedFindingSchema,
      findings: z.array(FeedFindingSchema),
      teamSnapshot: TeamSnapshotSchema,
      reportLeaderboard: ReportLeaderboardSchema,
    })
    .strict(),
  z
    .object({
      ...HomeBaseShape,
      ...StateMessageShape,
      status: z.literal("no_published_week"),
      throughWeek: z.null(),
    })
    .strict(),
  z
    .object({
      ...HomeBaseShape,
      ...StateMessageShape,
      status: z.literal("unavailable"),
      throughWeek: z.number().int().min(1).max(18).nullable(),
    })
    .strict(),
]);

const CurrentReportViewSchema = z
  .object({
    viewId: StableIdSchema,
    summary: ReportSummarySchema,
    rows: z.array(CurrentEvidenceRowSchema),
  })
  .strict();
const MovementReportViewSchema = z
  .object({
    viewId: StableIdSchema,
    summary: ReportSummarySchema,
    rows: z.array(MovementEvidenceRowSchema),
  })
  .strict();
const ReportSortOptionSchema = z
  .object({
    id: ReportSortSchema,
    label: z.string().min(1),
  })
  .strict();
const ReportMetadataShape = {
  ...BundleBaseShape,
  reportFamily: ReportFamilySchema,
  title: z.string().min(1),
  question: z.string().min(1),
  description: z.string().min(1),
  availableViews: z.array(ReportViewOptionSchema),
  defaultView: StableIdSchema,
  defaultSort: ReportSortSchema,
  availableSorts: z.array(ReportSortOptionSchema),
  teamOptions: z.array(StableIdSchema),
  resultCount: z.number().int().nonnegative(),
};

function currentReportSchema(
  schemaVersion:
    | "depthsnap.report.backfield.v1"
    | "depthsnap.report.targets.v1",
  family: "backfield_control" | "target_hierarchy",
) {
  return z.discriminatedUnion("status", [
    z
      .object({
        ...ReportMetadataShape,
        schemaVersion: z.literal(schemaVersion),
        reportFamily: z.literal(family),
        status: z.literal("published"),
        throughWeek: z.number().int().min(1).max(18),
        views: z.array(CurrentReportViewSchema),
      })
      .strict(),
    z
      .object({
        ...ReportMetadataShape,
        ...StateMessageShape,
        schemaVersion: z.literal(schemaVersion),
        reportFamily: z.literal(family),
        status: z.literal("no_published_week"),
        throughWeek: z.null(),
        views: z.array(CurrentReportViewSchema).length(0),
      })
      .strict(),
    z
      .object({
        ...ReportMetadataShape,
        ...StateMessageShape,
        schemaVersion: z.literal(schemaVersion),
        reportFamily: z.literal(family),
        status: z.literal("unavailable"),
        throughWeek: z.number().int().min(1).max(18).nullable(),
        views: z.array(CurrentReportViewSchema).length(0),
      })
      .strict(),
  ]);
}

export const BackfieldReportBundleSchema = currentReportSchema(
  "depthsnap.report.backfield.v1",
  "backfield_control",
);
export const TargetReportBundleSchema = currentReportSchema(
  "depthsnap.report.targets.v1",
  "target_hierarchy",
);
export const MovementReportBundleSchema = z.discriminatedUnion("status", [
  z
    .object({
      ...ReportMetadataShape,
      schemaVersion: z.literal("depthsnap.report.movement.v1"),
      reportFamily: z.literal("role_movement"),
      status: z.literal("published"),
      throughWeek: z.number().int().min(1).max(18),
      views: z.array(MovementReportViewSchema),
    })
    .strict(),
  z
    .object({
      ...ReportMetadataShape,
      ...StateMessageShape,
      schemaVersion: z.literal("depthsnap.report.movement.v1"),
      reportFamily: z.literal("role_movement"),
      status: z.literal("no_published_week"),
      throughWeek: z.null(),
      views: z.array(MovementReportViewSchema).length(0),
    })
    .strict(),
  z
    .object({
      ...ReportMetadataShape,
      ...StateMessageShape,
      schemaVersion: z.literal("depthsnap.report.movement.v1"),
      reportFamily: z.literal("role_movement"),
      status: z.literal("unavailable"),
      throughWeek: z.number().int().min(1).max(18).nullable(),
      views: z.array(MovementReportViewSchema).length(0),
    })
    .strict(),
]);

export const ReportsIndexModuleSchema = z.discriminatedUnion("kind", [
  z
    .object({
      kind: z.literal("current"),
      family: z.enum(["backfield_control", "target_hierarchy"]),
      title: z.string().min(1),
      question: z.string().min(1),
      description: z.string().min(1),
      href: HrefSchema,
      row: CurrentEvidenceRowSchema,
    })
    .strict(),
  z
    .object({
      kind: z.literal("movement"),
      family: z.literal("role_movement"),
      title: z.string().min(1),
      question: z.string().min(1),
      description: z.string().min(1),
      href: HrefSchema,
      row: MovementEvidenceRowSchema,
    })
    .strict(),
]);
export const ReportsIndexBundleSchema = z
  .object({
    ...BundleBaseShape,
    schemaVersion: z.literal("depthsnap.reports.index.v1"),
    modules: z.array(ReportsIndexModuleSchema),
  })
  .strict()
  .superRefine((bundle, context) => {
    if (bundle.status !== "published" && bundle.modules.length > 0) {
      context.addIssue({
        code: "custom",
        path: ["modules"],
        message: "non-published report indexes must not contain evidence modules",
      });
    }
  });

export const HierarchyEvidenceRowSchema = z
  .object({
    authoritativeOrder: z.number().int().positive(),
    player: PlayerIdentitySchema,
    roleFamily: z.string().min(1),
    evidence: RawShareEvidenceSchema,
    classificationLabel: z.string().min(1),
    dataQuality: DataQualitySchema,
  })
  .strict();

export const SuppliedMovementRecordSchema = z
  .object({
    authoritativeOrder: z.number().int().positive(),
    player: PlayerIdentitySchema,
    reportFamily: ReportFamilySchema,
    roleFamily: z.string().min(1),
    movement: MovementEvidenceSchema,
    direction: MovementDirectionSchema,
    finding: z.string().min(1),
    reportHref: HrefSchema,
    dataQuality: DataQualitySchema,
  })
  .strict();

export const ReportMembershipSchema = z
  .object({
    family: ReportFamilySchema,
    label: z.string().min(1),
    href: HrefSchema,
    authoritativeRank: z.number().int().positive(),
  })
  .strict();

export const TeamDirectoryRecordSchema = z
  .object({
    team: TeamIdentitySchema,
    topBackfield: HierarchyEvidenceRowSchema.optional(),
    topWr: HierarchyEvidenceRowSchema.optional(),
    topTe: HierarchyEvidenceRowSchema.optional(),
    largestMovement: SuppliedMovementRecordSchema.optional(),
  })
  .strict();

export const PlayerDirectoryRecordSchema = z
  .object({
    player: PlayerIdentitySchema,
    currentEvidence: RawShareEvidenceSchema.optional(),
    suppliedRoleDescription: z.string().min(1),
    memberships: z.array(ReportMembershipSchema),
    latestMovement: SuppliedMovementRecordSchema.optional(),
  })
  .strict();

export const WeeklyEvidencePointSchema = z
  .object({
    week: z.number().int().min(1).max(18),
    periodLabel: z.string().min(1),
    evidence: RawShareEvidenceSchema.optional(),
    opportunityLabel: OpportunityLabelSchema,
    dataQuality: DataQualitySchema,
    partialGame: z.boolean().optional(),
  })
  .strict();

const IdentityMetadataShape = {
  ...BundleBaseShape,
};
export const TeamsIndexBundleSchema = z
  .object({
    ...IdentityMetadataShape,
    schemaVersion: z.literal("depthsnap.teams.index.v1"),
    teams: z.array(TeamDirectoryRecordSchema),
  })
  .strict()
  .superRefine((bundle, context) => {
    if (bundle.status !== "published" && bundle.teams.length > 0) {
      context.addIssue({
        code: "custom",
        path: ["teams"],
        message: "non-published team indexes must not contain evidence rows",
      });
    }
  });
export const PlayersIndexBundleSchema = z
  .object({
    ...IdentityMetadataShape,
    schemaVersion: z.literal("depthsnap.players.index.v1"),
    players: z.array(PlayerDirectoryRecordSchema),
    teamOptions: z.array(StableIdSchema),
  })
  .strict()
  .superRefine((bundle, context) => {
    if (bundle.status !== "published" && bundle.players.length > 0) {
      context.addIssue({
        code: "custom",
        path: ["players"],
        message: "non-published player indexes must not contain evidence rows",
      });
    }
  });

export const TeamBundleSchema = z
  .object({
    ...IdentityMetadataShape,
    schemaVersion: z.literal("depthsnap.team.v1"),
    team: TeamIdentitySchema,
    suppliedSummary: z.string().min(1),
    backfieldHierarchy: z.array(HierarchyEvidenceRowSchema),
    wrTargetHierarchy: z.array(HierarchyEvidenceRowSchema),
    teTargetHierarchy: z.array(HierarchyEvidenceRowSchema),
    movements: z.array(SuppliedMovementRecordSchema),
    linkedPlayers: z.array(PlayerIdentitySchema),
    availableViews: z.array(z.string().min(1)),
    dataQuality: DataQualitySchema,
  })
  .strict()
  .superRefine((bundle, context) => {
    if (
      bundle.status !== "published" &&
      (bundle.backfieldHierarchy.length > 0 ||
        bundle.wrTargetHierarchy.length > 0 ||
        bundle.teTargetHierarchy.length > 0 ||
        bundle.movements.length > 0)
    ) {
      context.addIssue({
        code: "custom",
        path: ["status"],
        message: "non-published team bundles must not contain role evidence",
      });
    }
  });

export const PlayerBundleSchema = z
  .object({
    ...IdentityMetadataShape,
    schemaVersion: z.literal("depthsnap.player.v1"),
    player: PlayerIdentitySchema,
    currentTeam: TeamIdentitySchema,
    suppliedRoleDescription: z.string().min(1),
    currentEvidence: RawShareEvidenceSchema.optional(),
    supportingContext: SupportingContextSchema.optional(),
    latestMovement: SuppliedMovementRecordSchema.optional(),
    reportMemberships: z.array(ReportMembershipSchema),
    weeklyEvidence: z.array(WeeklyEvidencePointSchema),
    periodSummaries: z.array(
      z
        .object({
          label: z.string().min(1),
          evidence: RawShareEvidenceSchema,
        })
        .strict(),
    ),
    movementHistory: z.array(SuppliedMovementRecordSchema),
    teamHierarchyContext: z.array(HierarchyEvidenceRowSchema),
    dataQuality: DataQualitySchema,
  })
  .strict()
  .superRefine((bundle, context) => {
    if (
      bundle.status !== "published" &&
      (bundle.currentEvidence !== undefined ||
        bundle.supportingContext !== undefined ||
        bundle.latestMovement !== undefined ||
        bundle.reportMemberships.length > 0 ||
        bundle.weeklyEvidence.length > 0 ||
        bundle.periodSummaries.length > 0 ||
        bundle.movementHistory.length > 0 ||
        bundle.teamHierarchyContext.length > 0)
    ) {
      context.addIssue({
        code: "custom",
        path: ["status"],
        message: "non-published player bundles must not contain role evidence",
      });
    }
  });

export const SearchIdentitySchema = z
  .object({
    type: z.enum(["team", "player"]),
    id: StableIdSchema,
    displayName: z.string().min(1),
    secondaryLabel: z.string().min(1),
    summary: z.string().min(1),
    href: HrefSchema,
    searchAliases: z.array(z.string().min(1)),
  })
  .strict();
export const SearchBundleSchema = z
  .object({
    ...IdentityMetadataShape,
    schemaVersion: z.literal("depthsnap.search.v1"),
    records: z.array(SearchIdentitySchema),
  })
  .strict();

export const StatusCheckResultSchema = z.enum([
  "pass",
  "fail",
  "attention",
  "unavailable",
  "reviewed",
  "not_applicable",
]);
export const StatusCheckSchema = z
  .object({
    id: StableIdSchema,
    label: z.string().min(1),
    status: StatusCheckResultSchema,
    detail: z.string().min(1),
    required: z.boolean(),
    blocking: z.boolean(),
    numerator: z.number().int().nonnegative().optional(),
    denominator: z.number().int().nonnegative().optional(),
    percentage: z.number().min(0).max(100).optional(),
  })
  .strict()
  .superRefine((value, context) => {
    const hasNumerator = value.numerator !== undefined;
    const hasDenominator = value.denominator !== undefined;
    if (hasNumerator !== hasDenominator) {
      context.addIssue({
        code: "custom",
        path: [hasNumerator ? "denominator" : "numerator"],
        message: "coverage numerator and denominator must be supplied together",
      });
      return;
    }
    if (
      value.numerator !== undefined &&
      value.denominator !== undefined &&
      value.numerator > value.denominator
    ) {
      context.addIssue({
        code: "custom",
        path: ["numerator"],
        message: "coverage numerator must not exceed denominator",
      });
    }
    if (
      value.numerator !== undefined &&
      value.denominator !== undefined &&
      value.denominator > 0 &&
      value.percentage !== undefined
    ) {
      const expected = (value.numerator / value.denominator) * 100;
      if (Math.abs(value.percentage - expected) > 0.05) {
        context.addIssue({
          code: "custom",
          path: ["percentage"],
          message:
            "coverage percentage must match numerator / denominator within 0.05 percentage points",
        });
      }
    }
  });
export const StatusBundleSchema = z
  .object({
    ...BundleBaseShape,
    schemaVersion: z.literal("depthsnap.status.v1"),
    formulaVersion: z.string().min(1).optional(),
    pipelineRunId: z.string().min(1).optional(),
    manifestSchemaVersion: z.literal("depthsnap.manifest.v1"),
    bundleCount: z.number().int().nonnegative(),
    validationSummary: z.string().min(1),
    checks: z.array(StatusCheckSchema),
    limitations: z.array(z.string().min(1)),
  })
  .strict();

export const BundleFamilySchema = z.enum([
  "home",
  "reports_index",
  "report_backfield",
  "report_targets",
  "report_movement",
  "teams_index",
  "team",
  "players_index",
  "player",
  "search",
  "status",
]);
export const ManifestEntrySchema = z
  .object({
    family: BundleFamilySchema,
    id: StableIdSchema.optional(),
    path: z
      .string()
      .min(1)
      .refine(
        (path) =>
          !path.startsWith("/") &&
          !path.includes("\\") &&
          !path.split("/").includes(".."),
        "manifest paths must be safe relative POSIX paths",
      ),
    schemaVersion: z.string().min(1),
    sha256: z.string().regex(/^[a-f0-9]{64}$/),
    required: z.boolean(),
    recordCount: z.number().int().nonnegative(),
  })
  .strict();
export const ManifestSchema = z
  .object({
    schemaVersion: z.literal("depthsnap.manifest.v1"),
    productId: ProductIdSchema,
    dataMode: DataModeSchema,
    publicationStatus: PublicationStatusSchema,
    validationResult: PublicationValidationResultSchema,
    season: z.number().int().min(2000).max(2200),
    throughWeek: z.number().int().min(1).max(18).nullable(),
    generatedAt: TimestampSchema,
    sourceVersion: z.string().min(1),
    formulaVersion: z.string().min(1).optional(),
    pipelineRunId: z.string().min(1).optional(),
    entries: z.array(ManifestEntrySchema).min(1),
  })
  .strict();

export const LoaderFailureCategorySchema = z.enum([
  "bundle_missing",
  "invalid_json",
  "invalid_bundle",
  "incompatible_schema",
  "manifest_mismatch",
  "hash_mismatch",
  "unresolved_reference",
  "unsupported_data_mode",
]);
export const LoaderFailureSchema = z
  .object({
    category: LoaderFailureCategorySchema,
    title: z.string().min(1),
    message: z.string().min(1),
    publicDetail: z.string().min(1),
  })
  .strict();

export const BundleSchemas = {
  home: HomeBundleSchema,
  reports_index: ReportsIndexBundleSchema,
  report_backfield: BackfieldReportBundleSchema,
  report_targets: TargetReportBundleSchema,
  report_movement: MovementReportBundleSchema,
  teams_index: TeamsIndexBundleSchema,
  team: TeamBundleSchema,
  players_index: PlayersIndexBundleSchema,
  player: PlayerBundleSchema,
  search: SearchBundleSchema,
  status: StatusBundleSchema,
} as const;

export type DataMode = z.infer<typeof DataModeSchema>;
export type PublicationStatus = z.infer<typeof PublicationStatusSchema>;
export type PublicationValidationResult = z.infer<
  typeof PublicationValidationResultSchema
>;
export type DataQuality = z.infer<typeof DataQualitySchema>;
export type StatusCheckResult = z.infer<typeof StatusCheckResultSchema>;
export type RawShareEvidenceContract = z.infer<typeof RawShareEvidenceSchema>;
export type MovementEvidenceContract = z.infer<typeof MovementEvidenceSchema>;
export type HomeBundle = z.infer<typeof HomeBundleSchema>;
export type BackfieldReportBundle = z.infer<
  typeof BackfieldReportBundleSchema
>;
export type TargetReportBundle = z.infer<typeof TargetReportBundleSchema>;
export type MovementReportBundle = z.infer<typeof MovementReportBundleSchema>;
export type ReportBundle =
  | BackfieldReportBundle
  | TargetReportBundle
  | MovementReportBundle;
export type ReportsIndexBundle = z.infer<typeof ReportsIndexBundleSchema>;
export type TeamsIndexBundle = z.infer<typeof TeamsIndexBundleSchema>;
export type TeamBundle = z.infer<typeof TeamBundleSchema>;
export type PlayersIndexBundle = z.infer<typeof PlayersIndexBundleSchema>;
export type PlayerBundle = z.infer<typeof PlayerBundleSchema>;
export type SearchBundle = z.infer<typeof SearchBundleSchema>;
export type StatusBundle = z.infer<typeof StatusBundleSchema>;
export type Manifest = z.infer<typeof ManifestSchema>;
export type ManifestEntry = z.infer<typeof ManifestEntrySchema>;
export type BundleFamily = z.infer<typeof BundleFamilySchema>;
export type LoaderFailure = z.infer<typeof LoaderFailureSchema>;
