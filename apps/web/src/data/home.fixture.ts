import type {
  HomepageFixture,
  NoPublishedWeekHomepageFixture,
  ReportLink,
  UnavailableHomepageFixture,
} from "@/lib/types";

const reportLinks = [
  {
    family: "backfield_control",
    label: "Backfield Control",
    description: "Carries and total RB opportunities",
    href: "/reports/backfield",
  },
  {
    family: "target_hierarchy",
    label: "Target Hierarchy",
    description: "WR and TE target ownership",
    href: "/reports/targets",
  },
  {
    family: "role_movement",
    label: "Role Movement",
    description: "Before-versus-current evidence",
    href: "/reports/movement",
  },
] as const satisfies readonly ReportLink[];

const fixtureMetadata = {
  schemaVersion: "depthsnap.home.fixture.v1",
  fixture: true,
  fixtureNotice:
    "Design fixture data — synthetic records for interface review, not a current NFL week.",
  season: 2025,
  throughWeek: 18,
  generatedAt: "2026-07-23T12:00:00Z",
  reportLinks,
} as const;

export const publishedHomeFixture = {
  ...fixtureMetadata,
  status: "published",
  leadFinding: {
    id: "fixture-lead-backfield-control",
    kind: "backfield_increase",
    reportFamily: "backfield_control",
    roleFamily: "RB opportunity share",
    player: {
      id: "fixture-marcus-hale",
      name: "Marcus Hale",
      team: "JAX",
      position: "RB",
    },
    headline: "Marcus Hale took control of the team backfield.",
    current: {
      numerator: 27,
      denominator: 34,
      share: 0.794,
      opportunityLabel: "opportunities",
    },
    movement: {
      previous: {
        numerator: 18,
        denominator: 32,
        share: 0.563,
        opportunityLabel: "opportunities",
      },
      current: {
        numerator: 27,
        denominator: 34,
        share: 0.794,
        opportunityLabel: "opportunities",
      },
      percentagePointChange: 23.1,
    },
    evidenceHref: "/reports/backfield?player=fixture-marcus-hale",
  },
  findings: [
    {
      id: "fixture-backfield-increase",
      kind: "backfield_increase",
      reportFamily: "backfield_control",
      roleFamily: "RB opportunity share",
      player: {
        id: "fixture-zion-mercer",
        name: "Zion Mercer",
        team: "IND",
        position: "RB",
      },
      headline: "Moved into the lead backfield role.",
      current: {
        numerator: 22,
        denominator: 35,
        share: 0.629,
        opportunityLabel: "opportunities",
      },
      movement: {
        previous: {
          numerator: 12,
          denominator: 33,
          share: 0.364,
          opportunityLabel: "opportunities",
        },
        current: {
          numerator: 22,
          denominator: 35,
          share: 0.629,
          opportunityLabel: "opportunities",
        },
        percentagePointChange: 26.5,
      },
      evidenceHref: "/reports/backfield?player=fixture-zion-mercer",
    },
    {
      id: "fixture-target-share-increase",
      kind: "target_share_increase",
      reportFamily: "target_hierarchy",
      roleFamily: "WR target share",
      player: {
        id: "fixture-theo-lane",
        name: "Theo Lane",
        team: "SEA",
        position: "WR",
      },
      headline: "Claimed a larger share of the team target tree.",
      current: {
        numerator: 10,
        denominator: 31,
        share: 0.323,
        opportunityLabel: "targets",
      },
      movement: {
        previous: {
          numerator: 5,
          denominator: 29,
          share: 0.172,
          opportunityLabel: "targets",
        },
        current: {
          numerator: 10,
          denominator: 31,
          share: 0.323,
          opportunityLabel: "targets",
        },
        percentagePointChange: 15.1,
      },
      evidenceHref: "/reports/targets?player=fixture-theo-lane",
    },
    {
      id: "fixture-role-decline",
      kind: "role_decline",
      reportFamily: "role_movement",
      roleFamily: "RB carry share",
      player: {
        id: "fixture-miles-redd",
        name: "Miles Redd",
        team: "TB",
        position: "RB",
      },
      headline: "Lost a meaningful portion of the rushing workload.",
      current: {
        numerator: 8,
        denominator: 28,
        share: 0.286,
        opportunityLabel: "carries",
      },
      movement: {
        previous: {
          numerator: 15,
          denominator: 26,
          share: 0.577,
          opportunityLabel: "carries",
        },
        current: {
          numerator: 8,
          denominator: 28,
          share: 0.286,
          opportunityLabel: "carries",
        },
        percentagePointChange: -29.1,
      },
      evidenceHref: "/reports/movement?player=fixture-miles-redd",
    },
    {
      id: "fixture-concentrated-role",
      kind: "concentrated_role",
      reportFamily: "target_hierarchy",
      roleFamily: "TE target share",
      player: {
        id: "fixture-drew-keaton",
        name: "Drew Keaton",
        team: "MIN",
        position: "TE",
      },
      headline: "Owned a concentrated share of team tight end targets.",
      current: {
        numerator: 9,
        denominator: 11,
        share: 0.818,
        opportunityLabel: "targets",
      },
      evidenceHref: "/reports/targets?player=fixture-drew-keaton",
    },
    {
      id: "fixture-committee-formation",
      kind: "committee_formation",
      reportFamily: "role_movement",
      roleFamily: "RB opportunity share",
      player: {
        id: "fixture-owen-black",
        name: "Owen Black",
        team: "DEN",
        position: "RB",
      },
      headline: "The backfield moved away from a single lead role.",
      current: {
        numerator: 13,
        denominator: 30,
        share: 0.433,
        opportunityLabel: "opportunities",
      },
      movement: {
        previous: {
          numerator: 21,
          denominator: 29,
          share: 0.724,
          opportunityLabel: "opportunities",
        },
        current: {
          numerator: 13,
          denominator: 30,
          share: 0.433,
          opportunityLabel: "opportunities",
        },
        percentagePointChange: -29.1,
      },
      evidenceHref: "/reports/movement?player=fixture-owen-black",
    },
  ],
} as const satisfies HomepageFixture;

export const noPublishedWeekFixture = {
  ...fixtureMetadata,
  status: "no_published_week",
  stateTitle: "No completed week is published yet",
  stateMessage:
    "DepthSnap will show role findings after the authoritative pipeline validates and publishes a completed week.",
} as const satisfies NoPublishedWeekHomepageFixture;

export const unavailableHomeFixture = {
  ...fixtureMetadata,
  status: "unavailable",
  stateTitle: "Role data is temporarily unavailable",
  stateMessage:
    "The published bundle could not be read. No shares or findings are shown until validated data is available again.",
} as const satisfies UnavailableHomepageFixture;

export function getHomeFixture(
  requestedState?: string,
): HomepageFixture {
  if (requestedState === "empty") {
    return noPublishedWeekFixture;
  }

  if (requestedState === "unavailable") {
    return unavailableHomeFixture;
  }

  return publishedHomeFixture;
}
