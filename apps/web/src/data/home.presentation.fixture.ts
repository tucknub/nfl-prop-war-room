import type {
  ReportLeaderboardFixture,
  TeamSnapshotFixture,
} from "@/lib/presentation-types";

export const teamSnapshotFixture = {
  monogram: "JT",
  teamName: "Jacksonville Tide",
  teamCode: "JVT",
  week: 18,
  rows: [
    {
      role: "RB1",
      player: "Marcus Hale",
      evidence: {
        numerator: 27,
        denominator: 34,
        share: 0.794,
        opportunityLabel: "opportunities",
      },
      tone: "lead",
    },
    {
      role: "RB2",
      player: "Elijah North",
      evidence: {
        numerator: 6,
        denominator: 34,
        share: 0.176,
        opportunityLabel: "opportunities",
      },
      tone: "secondary",
    },
    {
      role: "WR1",
      player: "Jonah Pike",
      evidence: {
        numerator: 11,
        denominator: 32,
        share: 0.344,
        opportunityLabel: "targets",
      },
      tone: "lead",
    },
    {
      role: "TE1",
      player: "Cole Mercer",
      evidence: {
        numerator: 7,
        denominator: 32,
        share: 0.219,
        opportunityLabel: "targets",
      },
      tone: "secondary",
    },
  ],
  biggestMovement: {
    player: "Marcus Hale",
    summary: "RB opportunity share",
    percentagePointChange: 23.1,
    evidenceHref: "/reports/backfield?player=fixture-marcus-hale",
  },
  reportHref: "/teams?team=jvt",
} as const satisfies TeamSnapshotFixture;

export const reportLeaderboardFixture = {
  backfield_control: [
    {
      rank: 1,
      player: {
        id: "fixture-marcus-hale",
        name: "Marcus Hale",
        team: "JVT",
        position: "RB",
      },
      evidence: {
        numerator: 27,
        denominator: 34,
        share: 0.794,
        opportunityLabel: "opportunities",
      },
      movementPoints: 23.1,
      evidenceHref: "/reports/backfield?player=fixture-marcus-hale",
    },
    {
      rank: 2,
      player: {
        id: "fixture-caleb-stone",
        name: "Caleb Stone",
        team: "PDX",
        position: "RB",
      },
      evidence: {
        numerator: 25,
        denominator: 34,
        share: 0.735,
        opportunityLabel: "opportunities",
      },
      movementPoints: 8.6,
      evidenceHref: "/reports/backfield?player=fixture-caleb-stone",
    },
    {
      rank: 3,
      player: {
        id: "fixture-jordan-vale",
        name: "Jordan Vale",
        team: "BHM",
        position: "RB",
      },
      evidence: {
        numerator: 23,
        denominator: 33,
        share: 0.697,
        opportunityLabel: "opportunities",
      },
      movementPoints: 12.4,
      evidenceHref: "/reports/backfield?player=fixture-jordan-vale",
    },
    {
      rank: 4,
      player: {
        id: "fixture-micah-reed",
        name: "Micah Reed",
        team: "SAC",
        position: "RB",
      },
      evidence: {
        numerator: 21,
        denominator: 32,
        share: 0.656,
        opportunityLabel: "opportunities",
      },
      movementPoints: -3.2,
      evidenceHref: "/reports/backfield?player=fixture-micah-reed",
    },
    {
      rank: 5,
      player: {
        id: "fixture-devin-banks",
        name: "Devin Banks",
        team: "OKC",
        position: "RB",
      },
      evidence: {
        numerator: 19,
        denominator: 31,
        share: 0.613,
        opportunityLabel: "opportunities",
      },
      movementPoints: 5.4,
      evidenceHref: "/reports/backfield?player=fixture-devin-banks",
    },
  ],
  target_hierarchy: [
    {
      rank: 1,
      player: {
        id: "fixture-theo-lane",
        name: "Theo Lane",
        team: "SEA",
        position: "WR",
      },
      evidence: {
        numerator: 10,
        denominator: 31,
        share: 0.323,
        opportunityLabel: "targets",
      },
      movementPoints: 15.1,
      evidenceHref: "/reports/targets?player=fixture-theo-lane",
    },
    {
      rank: 2,
      player: {
        id: "fixture-jonah-pike",
        name: "Jonah Pike",
        team: "JVT",
        position: "WR",
      },
      evidence: {
        numerator: 11,
        denominator: 32,
        share: 0.344,
        opportunityLabel: "targets",
      },
      movementPoints: 6.7,
      evidenceHref: "/reports/targets?player=fixture-jonah-pike",
    },
    {
      rank: 3,
      player: {
        id: "fixture-drew-keaton",
        name: "Drew Keaton",
        team: "MIN",
        position: "TE",
      },
      evidence: {
        numerator: 9,
        denominator: 29,
        share: 0.31,
        opportunityLabel: "targets",
      },
      movementPoints: 4.2,
      evidenceHref: "/reports/targets?player=fixture-drew-keaton",
    },
    {
      rank: 4,
      player: {
        id: "fixture-luca-ward",
        name: "Luca Ward",
        team: "PDX",
        position: "WR",
      },
      evidence: {
        numerator: 9,
        denominator: 30,
        share: 0.3,
        opportunityLabel: "targets",
      },
      movementPoints: -2.9,
      evidenceHref: "/reports/targets?player=fixture-luca-ward",
    },
    {
      rank: 5,
      player: {
        id: "fixture-cole-mercer",
        name: "Cole Mercer",
        team: "JVT",
        position: "TE",
      },
      evidence: {
        numerator: 7,
        denominator: 32,
        share: 0.219,
        opportunityLabel: "targets",
      },
      movementPoints: 3.8,
      evidenceHref: "/reports/targets?player=fixture-cole-mercer",
    },
  ],
  role_movement: [
    {
      rank: 1,
      player: {
        id: "fixture-zion-mercer",
        name: "Zion Mercer",
        team: "IND",
        position: "RB",
      },
      evidence: {
        numerator: 22,
        denominator: 35,
        share: 0.629,
        opportunityLabel: "opportunities",
      },
      movementPoints: 26.5,
      evidenceHref: "/reports/movement?player=fixture-zion-mercer",
    },
    {
      rank: 2,
      player: {
        id: "fixture-marcus-hale",
        name: "Marcus Hale",
        team: "JVT",
        position: "RB",
      },
      evidence: {
        numerator: 27,
        denominator: 34,
        share: 0.794,
        opportunityLabel: "opportunities",
      },
      movementPoints: 23.1,
      evidenceHref: "/reports/movement?player=fixture-marcus-hale",
    },
    {
      rank: 3,
      player: {
        id: "fixture-theo-lane",
        name: "Theo Lane",
        team: "SEA",
        position: "WR",
      },
      evidence: {
        numerator: 10,
        denominator: 31,
        share: 0.323,
        opportunityLabel: "targets",
      },
      movementPoints: 15.1,
      evidenceHref: "/reports/movement?player=fixture-theo-lane",
    },
    {
      rank: 4,
      player: {
        id: "fixture-miles-redd",
        name: "Miles Redd",
        team: "TB",
        position: "RB",
      },
      evidence: {
        numerator: 8,
        denominator: 28,
        share: 0.286,
        opportunityLabel: "carries",
      },
      movementPoints: -29.1,
      evidenceHref: "/reports/movement?player=fixture-miles-redd",
    },
    {
      rank: 5,
      player: {
        id: "fixture-owen-black",
        name: "Owen Black",
        team: "DEN",
        position: "RB",
      },
      evidence: {
        numerator: 13,
        denominator: 30,
        share: 0.433,
        opportunityLabel: "opportunities",
      },
      movementPoints: -29.1,
      evidenceHref: "/reports/movement?player=fixture-owen-black",
    },
  ],
} as const satisfies ReportLeaderboardFixture;
