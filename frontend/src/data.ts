/* ============================================================================
   Mock data for the Discover dashboard.
   Shapes mirror what an AT Protocol / Tangled appview would return, so swapping
   these arrays for live firehose-derived records later is a drop-in change.
   ========================================================================== */

export type Lang = { name: string; color: string }

export const LANGS: Record<string, Lang> = {
  ts: { name: "TypeScript", color: "var(--lang-ts)" },
  go: { name: "Go", color: "var(--lang-go)" },
  rust: { name: "Rust", color: "var(--lang-rust)" },
  svelte: { name: "Svelte", color: "var(--lang-svelte)" },
  py: { name: "Python", color: "var(--lang-py)" },
  js: { name: "JavaScript", color: "var(--lang-js)" },
  zig: { name: "Zig", color: "var(--lang-zig)" },
}

export type ReasonKind = "lang" | "follow" | "topic" | "trending" | "similar"

export type Repo = {
  id: string
  owner: string
  name: string
  description: string
  lang: Lang
  stars: number
  issues: number
  pulls: number
  updated: string
  topics: string[]
  reason: string
  reasonKind: ReasonKind
}

export const RECOMMENDATIONS: Repo[] = [
  {
    id: "icyphox.sh/legit",
    owner: "icyphox.sh",
    name: "legit",
    description:
      "A web frontend for git, written in Go. Minimal, fast, and self-hostable — the lineage behind Tangled's own knots.",
    lang: LANGS.go,
    stars: 412,
    issues: 7,
    pulls: 3,
    updated: "2h ago",
    topics: ["git", "self-hosted", "atproto"],
    reason: "Matches your interest in Go + git tooling",
    reasonKind: "lang",
  },
  {
    id: "oppi.li/appview",
    owner: "oppi.li",
    name: "appview",
    description:
      "Reference AT Protocol appview that aggregates records off the firehose into a queryable index. Great starting point for agent integrations.",
    lang: LANGS.ts,
    stars: 286,
    issues: 12,
    pulls: 5,
    updated: "5h ago",
    topics: ["atproto", "firehose", "appview"],
    reason: "Popular with people you follow",
    reasonKind: "follow",
  },
  {
    id: "bigsky.dev/firehose-rs",
    owner: "bigsky.dev",
    name: "firehose-rs",
    description:
      "High-throughput Rust client for the AT Protocol firehose with backfill, cursors, and CBOR decoding. Powers several leaderboard bots.",
    lang: LANGS.rust,
    stars: 938,
    issues: 21,
    pulls: 9,
    updated: "1d ago",
    topics: ["rust", "firehose", "streaming"],
    reason: "Based on the 4 Rust repos you starred",
    reasonKind: "similar",
  },
  {
    id: "shulker.zip/listening_to",
    owner: "shulker.zip",
    name: "listening_to",
    description:
      "A Caddy plugin that adds a template to retrieve the currently playing track from a ListenBrainz profile.",
    lang: LANGS.go,
    stars: 64,
    issues: 2,
    pulls: 1,
    updated: "12m ago",
    topics: ["caddy", "music", "plugin"],
    reason: "Trending in your network",
    reasonKind: "trending",
  },
  {
    id: "tangled.org/core",
    owner: "tangled.org",
    name: "core",
    description:
      "The Tangled monorepo — knots, the appview, and the lexicons that make a code forge run natively on the AT Protocol.",
    lang: LANGS.go,
    stars: 1243,
    issues: 48,
    pulls: 17,
    updated: "8m ago",
    topics: ["atproto", "forge", "monorepo"],
    reason: "You use Tangled daily",
    reasonKind: "topic",
  },
  {
    id: "vvill.dev/caddy-atproto",
    owner: "vvill.dev",
    name: "caddy-atproto",
    description:
      "Caddy module to request and serve AT Protocol handle verification automatically — drop-in DID resolution for your domain.",
    lang: LANGS.go,
    stars: 148,
    issues: 4,
    pulls: 2,
    updated: "3h ago",
    topics: ["caddy", "atproto", "did"],
    reason: "Shares topics with repos you starred",
    reasonKind: "topic",
  },
]

export type Profile = {
  id: string
  handle: string
  displayName: string
  bio: string
  avatar: string // gradient css
  followers: number
  repos: number
  reason: string
}

export const SUGGESTED_PROFILES: Profile[] = [
  {
    id: "icyphox.sh",
    handle: "icyphox.sh",
    displayName: "Anirudh",
    bio: "Building git + ATProto tooling. Author of legit.",
    avatar: "linear-gradient(135deg, #1fb8a6, #189e8e)",
    followers: 2140,
    repos: 38,
    reason: "Followed by 3 people you follow",
  },
  {
    id: "oppi.li",
    handle: "oppi.li",
    displayName: "Oppi",
    bio: "Appview maintainer. Firehose enjoyer.",
    avatar: "linear-gradient(135deg, #6d6af6, #3b3aa8)",
    followers: 980,
    repos: 24,
    reason: "Maintains repos you starred",
  },
  {
    id: "bnewbold.net",
    handle: "bnewbold.net",
    displayName: "Bryan Newbold",
    bio: "AT Protocol core. Lexicons, DIDs, and the firehose.",
    avatar: "linear-gradient(135deg, #e0723a, #b8501f)",
    followers: 5600,
    repos: 51,
    reason: "Active in atproto",
  },
  {
    id: "lewis.tangled.sh",
    handle: "lewis.tangled.sh",
    displayName: "Lewis",
    bio: "Founding engineer @ Tangled. Knots, CI, protocol.",
    avatar: "linear-gradient(135deg, #00add8, #0077a3)",
    followers: 1810,
    repos: 29,
    reason: "Works on tools you use",
  },
  {
    id: "paul.bsky.team",
    handle: "paul.bsky.team",
    displayName: "Paul Frazee",
    bio: "Working on the AT Protocol & Bluesky. Local-first apps.",
    avatar: "linear-gradient(135deg, #6d6af6, #3b3aa8)",
    followers: 8900,
    repos: 67,
    reason: "Active in atproto",
  },
  {
    id: "nat.dev",
    handle: "nat.dev",
    displayName: "Nat",
    bio: "Maintains caddy-atproto. DID resolution nerd.",
    avatar: "linear-gradient(135deg, #1fb8a6, #189e8e)",
    followers: 740,
    repos: 19,
    reason: "Maintains repos you starred",
  },
  {
    id: "zola.cafe",
    handle: "zola.cafe",
    displayName: "Zola",
    bio: "Designing dev tools. Svelte + ATProto.",
    avatar: "linear-gradient(135deg, #e0723a, #b8501f)",
    followers: 1320,
    repos: 22,
    reason: "Followed by 2 people you follow",
  },
  {
    id: "samir.tngl.sh",
    handle: "samir.tngl.sh",
    displayName: "Samir",
    bio: "Local-first apps + CRDTs. Tangled power user.",
    avatar: "linear-gradient(135deg, #5a6b7a, #36424d)",
    followers: 560,
    repos: 14,
    reason: "Pushes to repos you watch",
  },
]

export type NotificationKind = "star" | "follow" | "pr" | "issue"

export type NotificationItem = {
  id: string
  actor: string
  action: string
  target: string
  time: string
  kind: NotificationKind
}

export const NOTIFICATIONS: NotificationItem[] = [
  {
    id: "n1",
    actor: "anirudh.tngl.sh",
    action: "starred",
    target: "qilun/atproto-kit",
    time: "8m ago",
    kind: "star",
  },
  {
    id: "n2",
    actor: "lewis.tangled.sh",
    action: "opened a PR on",
    target: "qilun/firehose-bot",
    time: "1h ago",
    kind: "pr",
  },
  {
    id: "n3",
    actor: "shulker.zip",
    action: "started following you",
    target: "",
    time: "3h ago",
    kind: "follow",
  },
  {
    id: "n4",
    actor: "oppi.li",
    action: "commented on issue #14 in",
    target: "qilun/atproto-kit",
    time: "5h ago",
    kind: "issue",
  },
]

export type RecentItem = {
  id: string
  owner: string
  name: string
  lang: Lang
  time: string
}

export const RECENTS: RecentItem[] = [
  { id: "r1", owner: "tangled.org", name: "core", lang: LANGS.go, time: "2m" },
  { id: "r2", owner: "oyster.cafe", name: "knot2", lang: LANGS.rust, time: "1h" },
  {
    id: "r3",
    owner: "qilun.tngl.sh",
    name: "atproto-kit",
    lang: LANGS.ts,
    time: "3h",
  },
  {
    id: "r4",
    owner: "bigsky.dev",
    name: "firehose-rs",
    lang: LANGS.rust,
    time: "yesterday",
  },
]

export const USER = {
  handle: "qilun.tngl.sh",
  avatar: "linear-gradient(135deg, #1fb8a6, #189e8e)",
}
