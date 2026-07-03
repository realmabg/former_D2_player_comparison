const DATA_URL = "./data/projection_dashboard_data.json";
const FORMER_PLAYERS_URL = "./data/former_d2_players.json";
const DEFAULT_DESTINATION = "Big West";
const DEFAULT_ROUTE = "leaderboard";

const ROUTES = [
  "raw-stats",
  "leaderboard",
  "pathways",
  "methodology",
  "recruiting-board",
];

const state = {
  data: null,
  players: [],
  formerPlayers: [],
  route: DEFAULT_ROUTE,
  destination: DEFAULT_DESTINATION,
  target: "bpr",
  destinationSchoolByConference: {},
  projectedMpgByConference: {},
  navOpen: false,
  search: {
    query: "",
    classYear: "All",
    conference: "All",
    position: "All",
    minBpr: -2,
  },
  leaderboard: {
    sort: "bpr",
    selectedId: null,
  },
  rawStats: {
    sort: "ppg",
    selectedId: null,
  },
  pathways: {
    formerId: null,
    selectedCurrentId: null,
  },
  modal: {
    playerId: null,
  },
  benchmarks: {},
};

const SIMILARITY_FEATURES = [
  { key: "height", weight: 1.3 },
  { key: "mpg", weight: 1.2 },
  { key: "ppg", weight: 1.15 },
  { key: "rpg", weight: 0.9 },
  { key: "apg", weight: 0.95 },
  { key: "spg", weight: 0.65 },
  { key: "bpg", weight: 0.6 },
  { key: "topg", weight: 0.35 },
  { key: "ptsPer40", weight: 1.15 },
  { key: "rebPer40", weight: 0.95 },
  { key: "astPer40", weight: 1.05 },
  { key: "stlPer40", weight: 1.1 },
  { key: "blkPer40", weight: 0.85 },
  { key: "tovPer40", weight: 0.35 },
  { key: "fgPct", weight: 0.45 },
  { key: "threePct", weight: 0.45 },
  { key: "ftPct", weight: 0.3 },
  { key: "efgPct", weight: 0.75 },
  { key: "tsPct", weight: 1.15 },
  { key: "threeRate", weight: 1.05 },
  { key: "ftRate", weight: 0.85 },
  { key: "sourceConfPower", weight: 0.7 },
  { key: "sourceTeamPower", weight: 0.6 },
];

const els = {
  viewRoot: document.querySelector("#viewRoot"),
  navList: document.querySelector("#navList"),
  sidebar: document.querySelector("#sidebar"),
  navOverlay: document.querySelector("#navOverlay"),
  menuToggle: document.querySelector("#menuToggle"),
  menuClose: document.querySelector("#menuClose"),
  quickCompare: document.querySelector("#quickCompare"),
};

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function formatNumber(value, digits = 1) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toFixed(digits) : "-";
}

function formatSigned(value, digits = 2) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "-";
  return `${number >= 0 ? "+" : ""}${number.toFixed(digits)}`;
}

function formatPct(value) {
  const number = Number(value);
  return Number.isFinite(number) ? `${Math.round(number * 100)}%` : "-";
}

function formatInteger(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toLocaleString() : "-";
}

function formatRatio(numerator, denominator, digits = 1) {
  const top = Number(numerator);
  const bottom = Number(denominator);
  if (!Number.isFinite(top) || !Number.isFinite(bottom) || bottom <= 0) return "-";
  const ratio = top / bottom;
  return ratio >= 10 ? ratio.toFixed(0) : ratio.toFixed(digits);
}

function projectionTier(target, value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "depth risk";
  if (target === "bpm_percentile") {
    if (number >= 80) return "impact starter";
    if (number >= 60) return "plus rotation";
    if (number >= 40) return "rotation";
    return "depth risk";
  }
  if (target === "porpag") {
    if (number >= 2.5) return "impact starter";
    if (number >= 1.5) return "plus rotation";
    if (number >= 0.5) return "rotation";
    return "depth risk";
  }
  if (number >= 4) return "impact starter";
  if (number >= 2) return "plus rotation";
  if (number >= 0) return "rotation";
  return "depth risk";
}

function initials(name) {
  return String(name ?? "")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

function uniqueSorted(values) {
  return [...new Set(values.filter(Boolean))].sort((a, b) => String(a).localeCompare(String(b)));
}

function normalizeClassFilterValue(value) {
  const text = String(value ?? "").trim().toLowerCase().replace(/\./g, "");
  if (text.startsWith("fr")) return "Fr";
  if (text.startsWith("so")) return "So";
  if (text.startsWith("jr")) return "Jr";
  if (text.startsWith("sr")) return "Sr";
  if (text.startsWith("gr")) return "Gr";
  return "Other";
}

function normalizeRoute(hash) {
  const route = hash.replace(/^#/, "") || DEFAULT_ROUTE;
  return ROUTES.includes(route) ? route : DEFAULT_ROUTE;
}

function minuteScenarioOptions() {
  return state.data?.meta?.minuteScenarioOptions ?? [10, 15, 20, 25, 30, 35];
}

function targetMeta(target = state.target) {
  return state.data?.meta?.projectionTargets?.[target] ?? {
    label: target.toUpperCase(),
    shortLabel: target.toUpperCase(),
  };
}

function targetOptionLabel(key, meta) {
  const label = meta?.label ?? key.toUpperCase();
  return key === "bpr" ? `${label} (recommended)` : label;
}

function targetOptions() {
  return Object.entries(state.data?.meta?.projectionTargets ?? {});
}

function renderPageHeader({ title, subtitle, stats = "" }) {
  return `
    <section class="page-header-card ${stats ? "" : "single"}">
      <div class="page-intro">
        <h1 class="page-title">${escapeHtml(title)}</h1>
        <p class="page-subtitle">${escapeHtml(subtitle)}</p>
      </div>
      ${stats}
    </section>
  `;
}

function benchmarkFor(statKey) {
  return state.benchmarks?.[statKey] ?? null;
}

function statInsight(player, statKey, digits = 1, asPct = false) {
  const benchmark = benchmarkFor(statKey);
  const value = Number(player?.[statKey]);
  if (!benchmark || !Number.isFinite(value)) return "";
  const avg = benchmark.mean;
  const delta = value - avg;
  const percentile = benchmark.percentileById?.[player.id];
  if (!Number.isFinite(avg) || !Number.isFinite(percentile)) return "";
  const deltaLabel = asPct ? `${delta >= 0 ? "+" : ""}${Math.round(delta * 100)} pts vs avg` : `${delta >= 0 ? "+" : ""}${delta.toFixed(digits)} vs avg`;
  return `${Math.round(percentile)}th pct · ${deltaLabel}`;
}

function renderStatCell({ label, value, insight = "" }) {
  return `
    <div>
      <span class="mini-label">${label}</span>
      <strong>${value}</strong>
      ${insight ? `<small class="stat-context">${escapeHtml(insight)}</small>` : ""}
    </div>
  `;
}

function destinationSchools(conference = state.destination) {
  return state.data?.meta?.destinationSchoolsByConference?.[conference] ?? [];
}

function defaultDestinationSchool(conference = state.destination) {
  return state.data?.meta?.defaultDestinationSchoolByConference?.[conference] ?? destinationSchools(conference)[0]?.slug ?? "";
}

function schoolContext(conference = state.destination, schoolSlug = defaultDestinationSchool(conference)) {
  return destinationSchools(conference).find((school) => school.slug === schoolSlug) ?? destinationSchools(conference)[0] ?? null;
}

function selectedDestinationSchool(conference = state.destination) {
  const selected = state.destinationSchoolByConference[conference];
  return schoolContext(conference, selected)?.slug ?? defaultDestinationSchool(conference);
}

function selectedProjectedMpg(conference = state.destination) {
  const selected = Number(state.projectedMpgByConference[conference]);
  const fallback = schoolContext(conference, selectedDestinationSchool(conference))?.defaultProjectedMpg ?? minuteScenarioOptions()[0];
  return Number.isFinite(selected) ? selected : fallback;
}

function interpolateProjection(target, targetProjection, schoolProjection, mpg) {
  if (!targetProjection) return null;
  const scenarios = targetProjection.minuteScenarios || {};
  const options = minuteScenarioOptions().slice().sort((a, b) => a - b);
  const clamped = Math.max(options[0], Math.min(options[options.length - 1], Number(mpg)));
  const lower = [...options].reverse().find((value) => value <= clamped) ?? options[0];
  const upper = options.find((value) => value >= clamped) ?? options[options.length - 1];
  const lowerBpr = Number(scenarios[String(lower)]);
  const upperBpr = Number(scenarios[String(upper)]);
  let bpr = lowerBpr;
  if (upper !== lower && Number.isFinite(lowerBpr) && Number.isFinite(upperBpr)) {
    const share = (clamped - lower) / (upper - lower);
    bpr = lowerBpr + (upperBpr - lowerBpr) * share;
  } else if (!Number.isFinite(lowerBpr) && Number.isFinite(upperBpr)) {
    bpr = upperBpr;
  }
  if (!Number.isFinite(bpr)) return null;
  return {
    bpr,
    tier: projectionTier(target, bpr),
    projectedMpg: clamped,
    destinationPower: schoolProjection.destinationPower,
    destinationTeamPower: schoolProjection.destinationTeamPower,
    schoolName: schoolProjection.name,
  };
}

function projectionFor(player, conference = state.destination, schoolSlug = selectedDestinationSchool(conference), mpg = selectedProjectedMpg(conference), target = state.target) {
  const conferenceProjection = player?.projections?.[conference] ?? null;
  if (!conferenceProjection) return null;
  const resolvedSchool = schoolSlug || conferenceProjection.defaultSchool;
  const schoolProjection =
    conferenceProjection.schools?.[resolvedSchool] ??
    conferenceProjection.schools?.[conferenceProjection.defaultSchool] ??
    Object.values(conferenceProjection.schools || {})[0] ??
    null;
  const targetProjection = schoolProjection?.targets?.[target] ?? null;
  return interpolateProjection(target, targetProjection, schoolProjection, mpg);
}

function currentProjection(player, conference = state.destination) {
  const best = player?.bestByTarget?.[state.target];
  return (
    projectionFor(player, conference, selectedDestinationSchool(conference), selectedProjectedMpg(conference), state.target) ??
    projectionFor(player, best?.conference, best?.destinationSchool, best?.projectedMpg, state.target) ??
    null
  );
}

function projectionEntries(player) {
  return Object.keys(player.projections || {})
    .map((conference) => [conference, currentProjection(player, conference)])
    .filter(([, projection]) => projection)
    .sort((a, b) => b[1].bpr - a[1].bpr);
}

function positionGroup(value) {
  const text = String(value ?? "").toLowerCase();
  if (text.includes("guard") || text === "g" || text === "pg" || text === "sg") return "G";
  if (text.includes("center") || text === "c") return "C";
  if (text.includes("forward") || text === "f" || text === "pf" || text === "sf") return "F";
  if (text === "gf" || text === "g/f") return "G/F";
  if (text === "fc" || text === "f/c") return "F/C";
  return String(value ?? "").toUpperCase() || "-";
}

function classRank(value) {
  const text = String(value ?? "").toLowerCase();
  if (text.startsWith("fr")) return 1;
  if (text.startsWith("so")) return 2;
  if (text.startsWith("jr")) return 3;
  if (text.startsWith("sr")) return 4;
  if (text.startsWith("gr")) return 5;
  return 0;
}

function isUcsdPathway(player) {
  return String(player?.destinationSchool ?? "").toLowerCase() === "uc san diego";
}

function sortedFormerPlayers() {
  return [...state.formerPlayers].sort((a, b) => {
    const aUcsd = Number(isUcsdPathway(a));
    const bUcsd = Number(isUcsdPathway(b));
    if (bUcsd !== aUcsd) return bUcsd - aUcsd;
    return a.name.localeCompare(b.name) || a.destinationSchool.localeCompare(b.destinationSchool);
  });
}

function buildSimilarityStats(players, features = SIMILARITY_FEATURES) {
  return features.reduce((stats, feature) => {
    const values = players
      .map((player) => Number(player?.[feature.key]))
      .filter((value) => Number.isFinite(value));
    if (!values.length) {
      stats[feature.key] = { mean: 0, std: 1 };
      return stats;
    }
    const mean = values.reduce((sum, value) => sum + value, 0) / values.length;
    const variance = values.reduce((sum, value) => sum + (value - mean) ** 2, 0) / values.length;
    stats[feature.key] = {
      mean,
      std: Math.sqrt(variance) || 1,
    };
    return stats;
  }, {});
}

function similarityScoreFromStats(target, candidate, stats, features = SIMILARITY_FEATURES) {
  if (!target || !candidate) return 0;
  let squaredDistance = 0;
  let weightTotal = 0;
  features.forEach((feature) => {
    const targetValue = Number(target?.[feature.key]);
    const candidateValue = Number(candidate?.[feature.key]);
    if (!Number.isFinite(targetValue) || !Number.isFinite(candidateValue)) return;
    const metric = stats[feature.key] ?? { mean: 0, std: 1 };
    const std = Number(metric.std) || 1;
    const delta = (targetValue - candidateValue) / std;
    const capped = Math.max(-3, Math.min(3, delta));
    squaredDistance += feature.weight * capped * capped;
    weightTotal += feature.weight;
  });
  if (!weightTotal) return 0;
  const distance = Math.sqrt(squaredDistance / weightTotal);
  let score = 100 - (distance / 2.6) * 100;
  const targetPosition = positionGroup(target.positionBucket || target.position);
  const candidatePosition = positionGroup(candidate.positionBucket || candidate.position);
  if (targetPosition === candidatePosition) score += 5;
  else if (targetPosition.includes(candidatePosition) || candidatePosition.includes(targetPosition)) score += 2;
  const classDelta = Math.abs(classRank(target.classYear) - classRank(candidate.classYear));
  if (classDelta === 0) score += 3;
  else if (classDelta === 1) score += 1.5;
  return Math.max(0, Math.min(100, Math.round(score)));
}

function rawStatValue(player, key) {
  switch (key) {
    case "games":
      return Number(player.games);
    case "mpg":
      return Number(player.mpg);
    case "ppg":
      return Number(player.ppg);
    case "rpg":
      return Number(player.rpg);
    case "apg":
      return Number(player.apg);
    case "ptsPer40":
      return Number(player.ptsPer40);
    case "rebPer40":
      return Number(player.rebPer40);
    case "astPer40":
      return Number(player.astPer40);
    case "threePct":
      return Number(player.threePct);
    case "sourceConfPower":
      return Number(player.sourceConfPower);
    case "name":
      return player.name;
    default:
      return Number(player[key]);
  }
}

function sortRawPlayers(players, key = "ppg") {
  const copy = [...players];
  copy.sort((a, b) => {
    if (key === "name") return a.name.localeCompare(b.name);
    if (key === "conference") return a.conference.localeCompare(b.conference) || a.team.localeCompare(b.team);
    return (rawStatValue(b, key) || 0) - (rawStatValue(a, key) || 0);
  });
  return copy;
}

function selectedFormerPathwayPlayer() {
  const sorted = sortedFormerPlayers();
  return sorted.find((player) => player.id === state.pathways.formerId) ?? sorted[0] ?? null;
}

function similarCurrentPlayers(former) {
  const stats = buildSimilarityStats([...state.players, ...state.formerPlayers]);
  return [...state.players]
    .map((current) => ({ ...current, similarity: similarityScoreFromStats(former, current, stats) }))
    .sort((a, b) => {
      if (b.similarity !== a.similarity) return b.similarity - a.similarity;
      const projectionB = currentProjection(b);
      const projectionA = currentProjection(a);
      return (projectionB?.bpr ?? -999) - (projectionA?.bpr ?? -999);
    });
}

function similarPeerPlayers(player) {
  const stats = buildSimilarityStats(state.players);
  return [...state.players]
    .filter((candidate) => candidate.id !== player.id)
    .map((candidate) => ({
      ...candidate,
      similarity: similarityScoreFromStats(player, candidate, stats),
    }))
    .sort((a, b) => {
      if (b.similarity !== a.similarity) return b.similarity - a.similarity;
      return (currentProjection(b)?.bpr ?? -999) - (currentProjection(a)?.bpr ?? -999);
    });
}

function buildBenchmarks(players) {
  const statKeys = [
    "games",
    "mpg",
    "ppg",
    "rpg",
    "apg",
    "spg",
    "bpg",
    "topg",
    "fgPct",
    "threePct",
    "ftPct",
    "efgPct",
    "tsPct",
    "threeRate",
    "ftRate",
    "ptsPer40",
    "rebPer40",
    "astPer40",
    "stlPer40",
    "blkPer40",
    "tovPer40",
    "sourceConfPower",
    "sourceTeamPower",
  ];
  return Object.fromEntries(
    statKeys.map((key) => {
      const values = players
        .map((player) => ({ id: player.id, value: Number(player?.[key]) }))
        .filter((entry) => Number.isFinite(entry.value))
        .sort((a, b) => a.value - b.value);
      if (!values.length) return [key, null];
      const mean = values.reduce((sum, entry) => sum + entry.value, 0) / values.length;
      const percentileById = Object.fromEntries(
        values.map((entry, index) => [entry.id, ((index + 1) / values.length) * 100])
      );
      return [key, { mean, percentileById }];
    })
  );
}

function filteredPlayers({ applyProjectionMin = true } = {}) {
  const query = state.search.query.trim().toLowerCase();
  return state.players.filter((player) => {
    const projection = currentProjection(player);
    if (!projection) return false;
    if (query) {
      const haystack = `${player.name} ${player.team} ${player.conference} ${player.position}`.toLowerCase();
      if (!haystack.includes(query)) return false;
    }
    if (state.search.classYear !== "All" && normalizeClassFilterValue(player.classYear) !== state.search.classYear) return false;
    if (state.search.conference !== "All" && player.conference !== state.search.conference) return false;
    if (state.search.position !== "All" && player.position !== state.search.position) return false;
    if (applyProjectionMin && projection.bpr < state.search.minBpr) return false;
    return true;
  });
}

function sortPlayers(players, key = "bpr") {
  const copy = [...players];
  copy.sort((a, b) => {
    if (key === "name") return a.name.localeCompare(b.name);
    if (key === "ppg") return b.ppg - a.ppg;
    if (key === "mpg") return b.mpg - a.mpg;
    return currentProjection(b).bpr - currentProjection(a).bpr;
  });
  return copy;
}

function topPlayers(limit = 6) {
  return sortPlayers(filteredPlayers(), "bpr").slice(0, limit);
}

function positionBadge(player) {
  return `<span class="position-badge">${escapeHtml(player.position)}</span>`;
}

function routeLink(route, label) {
  return `<a class="section-link" href="#${route}">${escapeHtml(label)} <span>→</span></a>`;
}

function renderDestinationContextControls({
  showConference = true,
  compact = false,
  title = "Projection context",
} = {}) {
  const conference = state.destination;
  const target = state.target;
  const schools = destinationSchools(conference);
  const schoolSlug = selectedDestinationSchool(conference);
  const school = schoolContext(conference, schoolSlug);
  const projectedMpg = selectedProjectedMpg(conference);
  const options = minuteScenarioOptions();
  return `
    <section class="content-card context-card ${compact ? "compact" : ""}">
      <div class="context-card-head">
        <div>
          <span class="section-label">${escapeHtml(title)}</span>
          <p class="support-copy">Choose the target metric, D1 landing spot, and expected year-one minutes you want the board to score against.</p>
        </div>
        <div class="context-meta">
          <strong>${escapeHtml(school?.name ?? conference)}</strong>
          <span>${escapeHtml(targetMeta(target).shortLabel)} · ${formatNumber(projectedMpg, 0)} MPG assumption</span>
        </div>
      </div>
      <div class="context-controls ${showConference ? "" : "school-only"}">
        <label>
          <span class="mini-label">Target metric</span>
          <select id="targetPicker" class="select-input">
            ${targetOptions().map(([key, meta]) => `<option value="${escapeHtml(key)}" ${key === target ? "selected" : ""}>${escapeHtml(targetOptionLabel(key, meta))}</option>`).join("")}
          </select>
        </label>
        ${showConference ? `
          <label>
            <span class="mini-label">Conference</span>
            <select id="destinationPicker" class="select-input">
              ${state.data.meta.conferences.map((item) => `<option value="${escapeHtml(item)}" ${item === conference ? "selected" : ""}>${escapeHtml(item)}</option>`).join("")}
            </select>
          </label>
        ` : ""}
        <label>
          <span class="mini-label">Destination team</span>
          <select id="destinationSchoolPicker" class="select-input">
            ${schools.map((item) => `<option value="${escapeHtml(item.slug)}" ${item.slug === schoolSlug ? "selected" : ""}>${escapeHtml(item.name)}</option>`).join("")}
          </select>
        </label>
        <label class="range-control">
          <span class="mini-label">Projected D1 MPG</span>
          <input
            id="projectedMpgRange"
            class="range-input"
            type="range"
            min="${options[0]}"
            max="${options[options.length - 1]}"
            step="1"
            value="${escapeHtml(projectedMpg)}"
          />
          <div class="range-scale">
            <strong id="projectedMpgValue">${formatNumber(projectedMpg, 0)} MPG</strong>
            <span>Interpolated between model checkpoints at ${options.join(", ")} MPG</span>
          </div>
        </label>
      </div>
    </section>
  `;
}

function summaryStats(players = state.players) {
  const visible = filteredPlayers();
  const top = sortPlayers(visible, "bpr")[0];
  const avg = visible.length
    ? visible.reduce((sum, player) => sum + currentProjection(player).bpr, 0) / visible.length
    : null;
  const school = schoolContext(state.destination, selectedDestinationSchool(state.destination));

  return `
    <section class="stat-grid" aria-label="Summary stats">
      <article class="stat-card">
        <span>Tracked prospects</span>
        <strong>${formatInteger(players.length)}</strong>
        <p>Current D2 players in the model</p>
      </article>
      <article class="stat-card">
        <span>Avg. projected ${escapeHtml(targetMeta().shortLabel)}</span>
        <strong>${avg === null ? "-" : formatSigned(avg)}</strong>
        <p>${escapeHtml(school?.name ?? state.destination)} at ${formatNumber(selectedProjectedMpg(state.destination), 0)} MPG</p>
      </article>
      <article class="stat-card">
        <span>Top projection</span>
        <strong>${top ? formatSigned(currentProjection(top).bpr) : "-"}</strong>
        <p>${top ? escapeHtml(top.name) : "No matching players"}</p>
      </article>
    </section>
  `;
}

function renderPlayerCard(player) {
  const projection = currentProjection(player);
  const school = schoolContext(state.destination, selectedDestinationSchool(state.destination));
  const projectedMpg = selectedProjectedMpg(state.destination);
  return `
    <article class="player-card">
      <div class="player-card-head">
        <div class="player-card-head-main">
          <div class="player-avatar">${escapeHtml(initials(player.name))}</div>
          <div class="player-card-head-copy">
            <h3>${escapeHtml(player.name)}</h3>
            <p class="player-subline">${escapeHtml(player.team)}</p>
            <span class="meta-line">${escapeHtml(player.classYear)} · ${escapeHtml(player.heightLabel)}</span>
          </div>
        </div>
        ${positionBadge(player)}
      </div>
      <div class="player-stat-row">
        <div><strong>${formatNumber(player.ppg, 1)}</strong><span>PPG</span></div>
        <div><strong>${formatNumber(player.rpg, 1)}</strong><span>RPG</span></div>
        <div><strong>${formatNumber(player.games, 0)}</strong><span>GP</span></div>
      </div>
      <div class="player-card-footer">
      <div>
          <span class="footer-label">Proj. ${escapeHtml(targetMeta().shortLabel)}</span>
          <div class="badge primary" style="margin-top:8px">${formatSigned(projection.bpr)}</div>
          <p class="quality-note">${escapeHtml(school?.name ?? state.destination)} · ${formatNumber(projectedMpg, 0)} MPG</p>
        </div>
        <div class="player-status">
          <p><span class="mini-label">Going to</span> ${escapeHtml(projection.schoolName ?? school?.name ?? "-")}</p>
          <p>${escapeHtml(player.bestByTarget?.[state.target]?.conference ?? "-")} best default fit</p>
        </div>
      </div>
    </article>
  `;
}

function projectionFilterOptions() {
  if (state.target === "bpm_percentile") return [0, 20, 40, 60, 80];
  if (state.target === "porpag") return [-1, 0, 0.5, 1, 2, 3];
  if (state.target === "bpm") return [-2, 0, 1, 2, 4, 6];
  return [-2, -1, 0, 1, 2, 3];
}

function searchToolbar({ addTargetFilter = true, sortButtons = [], sticky = false } = {}) {
  const classYears = ["All", ...uniqueSorted(state.players.map((player) => normalizeClassFilterValue(player.classYear)))];
  const conferences = ["All", ...uniqueSorted(state.players.map((player) => player.conference))];
  const positions = ["All", ...uniqueSorted(state.players.map((player) => player.position))];

  return `
    <section class="content-card ${sticky ? "sticky-filters" : ""}">
      <div class="toolbar">
        <div class="toolbar-left">
          <input id="searchQuery" class="search-input" type="search" placeholder="Search player, team, conference, or position" value="${escapeHtml(state.search.query)}" />
        </div>
        <div class="toolbar-right">
          ${sortButtons.length ? `
            <div class="sort-chip-group">
              <span class="mini-label">Sort by</span>
              <div class="chip-filter-list">
                ${sortButtons.map((button) => `
                  <button class="filter-chip ${button.active ? "active" : ""}" type="button" ${button.attr}="${escapeHtml(button.value)}">${escapeHtml(button.label)}</button>
                `).join("")}
              </div>
            </div>
          ` : ""}
          <button id="resetSearch" class="pill-button" type="button">Reset filters</button>
        </div>
      </div>
      <div class="filter-grid">
        ${renderSelect("searchClass", classYears, state.search.classYear)}
        ${renderSelect("searchConference", conferences, state.search.conference)}
        ${renderSelect("searchPosition", positions, state.search.position)}
        ${addTargetFilter ? `
          <label>
            <span class="mini-label">Min ${escapeHtml(targetMeta().shortLabel)}</span>
            <select id="searchMinBpr" class="select-input">
              ${projectionFilterOptions().map((value) => `<option value="${value}" ${Number(value) === Number(state.search.minBpr) ? "selected" : ""}>${value}</option>`).join("")}
            </select>
          </label>
        ` : ""}
      </div>
    </section>
  `;
}

async function loadFormerPlayersFallback() {
  const response = await fetch(FORMER_PLAYERS_URL);
  if (!response.ok) return [];
  const payload = await response.json();
  return Array.isArray(payload) ? payload : [];
}

function renderSelect(id, values, selected) {
  return `
    <label>
      <span class="mini-label">${escapeHtml(id.replace(/^search/, "").replace(/([A-Z])/g, " $1").trim() || id)}</span>
      <select id="${id}" class="select-input">
        ${values.map((value) => `<option value="${escapeHtml(value)}" ${value === selected ? "selected" : ""}>${escapeHtml(value)}</option>`).join("")}
      </select>
    </label>
  `;
}

function renderEmptyState(title, copy) {
  return `
    <div class="empty-state">
      <strong>${escapeHtml(title)}</strong>
      <p>${escapeHtml(copy)}</p>
    </div>
  `;
}

function renderLoadingState(title = "Loading projections...", copy = "Reading the model output and building the board.") {
  return `
    <section class="view">
      <div class="page-intro">
        <h1 class="page-title">${escapeHtml(title)}</h1>
        <p class="page-subtitle">${escapeHtml(copy)}</p>
      </div>
      <section class="content-card loading-card">
        <div class="loading-bar"></div>
        <div class="loading-grid">
          <div></div>
          <div></div>
          <div></div>
        </div>
      </section>
    </section>
  `;
}

function renderLeaderboardControls(players, selected) {
  return `
    <section class="content-card compact-controls">
      <div class="compact-control-grid">
        <label>
          <span class="mini-label">Metric</span>
          <select id="targetPicker" class="select-input compact-select">
            ${targetOptions().map(([key, meta]) => `<option value="${escapeHtml(key)}" ${key === state.target ? "selected" : ""}>${escapeHtml(targetOptionLabel(key, meta))}</option>`).join("")}
          </select>
        </label>
        <label>
          <span class="mini-label">Player</span>
          <select id="leaderboardPlayerPicker" class="select-input compact-select">
            ${players.slice(0, 200).map((player) => `<option value="${escapeHtml(player.id)}" ${player.id === selected?.id ? "selected" : ""}>${escapeHtml(player.name)} · ${escapeHtml(player.team)}</option>`).join("")}
          </select>
        </label>
      </div>
    </section>
  `;
}

function renderPathwayControls(former) {
  const formerOptions = sortedFormerPlayers();
  return `
    <section class="content-card compact-controls">
      <div class="compact-control-grid">
        <label>
          <span class="mini-label">Metric</span>
          <select id="targetPicker" class="select-input compact-select">
            ${targetOptions().map(([key, meta]) => `<option value="${escapeHtml(key)}" ${key === state.target ? "selected" : ""}>${escapeHtml(targetOptionLabel(key, meta))}</option>`).join("")}
          </select>
        </label>
        <label>
          <span class="mini-label">Player</span>
          <select id="pathwayFormerPlayer" class="select-input compact-select">
            <option value="">Select a historical comp</option>
            ${formerOptions.map((player) => `<option value="${escapeHtml(player.id)}" ${player.id === former?.id ? "selected" : ""}>${escapeHtml(player.name)} · ${escapeHtml(player.sourceSchool)} to ${escapeHtml(player.destinationSchool)}</option>`).join("")}
          </select>
        </label>
      </div>
    </section>
  `;
}

function renderLeaderboard() {
  const players = sortPlayers(filteredPlayers(), state.leaderboard.sort);
  const selected = players.find((player) => player.id === state.leaderboard.selectedId) ?? players[0] ?? null;
  if (selected && !state.leaderboard.selectedId) state.leaderboard.selectedId = selected.id;

  return `
    <section class="view view-leaderboard">
      ${renderPageHeader({
        title: "Projections",
        subtitle: `Ranked ${targetMeta().shortLabel} projections in the current destination-team context, with player detail and fit breakdown.`,
        stats: summaryStats(),
      })}
      ${renderDestinationContextControls({ title: "Projection scenario", compact: true })}
      ${searchToolbar({
        sortButtons: [
          { attr: "data-sort", value: "bpr", label: `Proj. ${targetMeta().shortLabel}`, active: state.leaderboard.sort === "bpr" },
          { attr: "data-sort", value: "ppg", label: "PPG", active: state.leaderboard.sort === "ppg" },
          { attr: "data-sort", value: "mpg", label: "MPG", active: state.leaderboard.sort === "mpg" },
          { attr: "data-sort", value: "name", label: "Name", active: state.leaderboard.sort === "name" },
        ],
      })}
      <section class="split-layout">
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Player</th>
                <th>Team</th>
                <th>GP</th>
                <th>PPG</th>
                <th>MPG</th>
                <th>Proj. ${escapeHtml(targetMeta().shortLabel)}</th>
              </tr>
            </thead>
            <tbody>
              ${players.slice(0, 150).map((player, index) => renderLeaderboardRow(player, index, selected?.id)).join("")}
            </tbody>
          </table>
        </div>
        ${selected ? renderLeaderRail(selected) : renderEmptyState("No player selected.", "Choose a player from the leaderboard to inspect their profile.")}
      </section>
    </section>
  `;
}

function renderLeaderRail(player) {
  return `
    <div class="detail-rail">
      ${renderLeaderDetail(player)}
      ${renderSimilarPlayersPanel(player)}
    </div>
  `;
}

function renderLeaderboardRow(player, index, selectedId) {
  const projection = currentProjection(player);
  return `
    <tr class="${player.id === selectedId ? "selected" : ""}" data-player-row="${escapeHtml(player.id)}">
      <td>${index + 1}</td>
      <td>
        <strong>${escapeHtml(player.name)}</strong><br />
        <span class="muted">${escapeHtml(player.position)} · ${escapeHtml(player.classYear)}</span>
      </td>
      <td>${escapeHtml(player.team)}</td>
      <td>${formatNumber(player.games, 0)}</td>
      <td>${formatNumber(player.ppg, 1)}</td>
      <td>${formatNumber(player.mpg, 1)}</td>
      <td><strong>${formatSigned(projection.bpr)}</strong><br /><span class="muted">${escapeHtml(projection.schoolName ?? "-")}</span></td>
    </tr>
  `;
}

function renderLeaderDetail(player) {
  const projection = currentProjection(player);
  const school = schoolContext(state.destination, selectedDestinationSchool(state.destination));
  return `
    <aside class="leader-detail">
      <div>
        <span class="section-label">${escapeHtml(player.team)} · ${escapeHtml(player.conference)}</span>
        <h3>${escapeHtml(player.name)}</h3>
        <p class="compare-subtitle">${escapeHtml(player.position)} · ${escapeHtml(player.heightLabel)} · ${escapeHtml(player.classYear)}</p>
      </div>
      <div class="score-card">
        <span class="section-label">${escapeHtml(state.destination)} · ${escapeHtml(school?.name ?? "")}</span>
        <strong>${formatSigned(projection.bpr)}</strong>
        <p>${escapeHtml(projection.tier)} at ${formatNumber(projection.projectedMpg, 0)} MPG</p>
      </div>
      <div class="projection-stack">
        ${projectionEntries(player).map(([conference, info]) => `
          <button class="projection-pill ${conference === state.destination ? "active" : ""}" type="button" data-destination="${escapeHtml(conference)}">
            <span>${escapeHtml(conference)}</span>
            <strong>${formatSigned(info.bpr)}</strong>
          </button>
        `).join("")}
      </div>
      <div class="detail-stat-grid">
        ${[
          { label: "Going to", value: escapeHtml(projection.schoolName ?? "-") },
          { label: "GP", value: formatNumber(player.games, 0), insight: statInsight(player, "games", 0) },
          { label: "PPG", value: formatNumber(player.ppg, 1), insight: statInsight(player, "ppg", 1) },
          { label: "RPG", value: formatNumber(player.rpg, 1), insight: statInsight(player, "rpg", 1) },
          { label: "APG", value: formatNumber(player.apg, 1), insight: statInsight(player, "apg", 1) },
          { label: "TS%", value: formatPct(player.tsPct), insight: statInsight(player, "tsPct", 1, true) },
          { label: "3P Rate", value: formatPct(player.threeRate), insight: statInsight(player, "threeRate", 1, true) },
          { label: "FT Rate", value: formatPct(player.ftRate), insight: statInsight(player, "ftRate", 1, true) },
          { label: "PTS/40", value: formatNumber(player.ptsPer40, 1), insight: statInsight(player, "ptsPer40", 1) },
          { label: "REB/40", value: formatNumber(player.rebPer40, 1), insight: statInsight(player, "rebPer40", 1) },
          { label: "AST/40", value: formatNumber(player.astPer40, 1), insight: statInsight(player, "astPer40", 1) },
          { label: "3P%", value: formatPct(player.threePct), insight: statInsight(player, "threePct", 1, true) },
          { label: "eFG%", value: formatPct(player.efgPct), insight: statInsight(player, "efgPct", 1, true) },
          { label: "D2 Pwr", value: formatNumber(player.sourceConfPower, 2), insight: statInsight(player, "sourceConfPower", 2) },
          { label: "Dest Team Pwr", value: formatNumber(projection.destinationTeamPower, 2) },
          { label: targetMeta().shortLabel, value: formatSigned(projection.bpr) },
        ].map(renderStatCell).join("")}
      </div>
    </aside>
  `;
}

function renderSimilarPlayersPanel(player) {
  const peers = similarPeerPlayers(player).slice(0, 8);
  return `
    <aside class="content-card similar-panel">
      <div class="section-block">
        <span class="section-label">Most Similar Players</span>
        <h3>Current D2 peers</h3>
        <p class="quality-note">Rate-aware z-score similarity using workload, production, shooting efficiency, shot mix, and conference/team context.</p>
      </div>
      <div class="similar-player-list">
        ${peers.map((peer) => {
          const projection = currentProjection(peer);
          return `
            <button class="similar-player-button" type="button" data-open-player-modal="${escapeHtml(peer.id)}">
              <span>
                <strong>${escapeHtml(peer.name)}</strong>
                <span class="muted">${escapeHtml(peer.team)} · ${formatNumber(peer.ppg, 1)} PPG · ${formatPct(peer.tsPct)} TS</span>
              </span>
              <span class="similar-player-meta">
                <strong>${formatNumber(peer.similarity, 0)}</strong>
                <span class="muted">${projection ? formatSigned(projection.bpr) : "-"}</span>
              </span>
            </button>
          `;
        }).join("") || `<div class="empty-state"><strong>No similar players</strong><p>There were not enough comparable profiles in the current pool.</p></div>`}
      </div>
    </aside>
  `;
}

function renderRawStats() {
  const players = sortRawPlayers(filteredPlayers({ applyProjectionMin: false }), state.rawStats.sort);
  const selected = players.find((player) => player.id === state.rawStats.selectedId) ?? players[0] ?? null;
  if (selected && !state.rawStats.selectedId) state.rawStats.selectedId = selected.id;
  return `
    <section class="view view-raw">
      ${renderPageHeader({
        title: "Raw Stats",
        subtitle: "Browse the current D2 player pool without the projection layer. Click a card to open the full stat profile.",
      })}
      ${searchToolbar({
        addTargetFilter: false,
        sticky: true,
        sortButtons: [
          { attr: "data-raw-sort", value: "ppg", label: "PPG", active: state.rawStats.sort === "ppg" },
          { attr: "data-raw-sort", value: "mpg", label: "MPG", active: state.rawStats.sort === "mpg" },
          { attr: "data-raw-sort", value: "rpg", label: "RPG", active: state.rawStats.sort === "rpg" },
          { attr: "data-raw-sort", value: "apg", label: "APG", active: state.rawStats.sort === "apg" },
          { attr: "data-raw-sort", value: "ptsPer40", label: "PTS/40", active: state.rawStats.sort === "ptsPer40" },
          { attr: "data-raw-sort", value: "name", label: "Name", active: state.rawStats.sort === "name" },
        ],
      })}
      <section class="split-layout">
        <div class="raw-card-grid">
          ${players.slice(0, 150).map((player) => `
            <button class="raw-player-card ${player.id === selected?.id ? "selected" : ""}" type="button" data-raw-player-row="${escapeHtml(player.id)}">
              <div class="raw-player-card-head">
                <div>
                  <strong>${escapeHtml(player.name)}</strong>
                  <p class="muted">${escapeHtml(player.team)}</p>
                  <p class="muted">${escapeHtml(player.conference)} · ${escapeHtml(player.position)} · ${escapeHtml(player.classYear)}</p>
                </div>
              </div>
              <div class="raw-player-primary-stats">
                <div><span class="mini-label">PPG</span><strong>${formatNumber(player.ppg, 1)}</strong></div>
                <div><span class="mini-label">3P%</span><strong>${formatPct(player.threePct)}</strong></div>
                <div><span class="mini-label">A/TO</span><strong>${formatRatio(player.apg, player.topg)}</strong></div>
              </div>
            </button>
          `).join("")}
        </div>
        ${selected ? renderRawStatsDetail(selected) : renderEmptyState("No player selected.", "Choose a player card to inspect the full profile.")} 
      </section>
    </section>
  `;
}

function renderRawStatsDetail(player) {
  return `
    <aside class="leader-detail">
      <div>
        <span class="section-label">${escapeHtml(player.team)} · ${escapeHtml(player.conference)}</span>
        <h3>${escapeHtml(player.name)}</h3>
        <p class="compare-subtitle">${escapeHtml(player.position)} · ${escapeHtml(player.heightLabel)} · ${escapeHtml(player.classYear)}</p>
      </div>
      <div class="detail-stat-grid">
        ${[
          { label: "GP", value: formatNumber(player.games, 0), insight: statInsight(player, "games", 0) },
          { label: "PPG", value: formatNumber(player.ppg, 1), insight: statInsight(player, "ppg", 1) },
          { label: "MPG", value: formatNumber(player.mpg, 1), insight: statInsight(player, "mpg", 1) },
          { label: "RPG", value: formatNumber(player.rpg, 1), insight: statInsight(player, "rpg", 1) },
          { label: "APG", value: formatNumber(player.apg, 1), insight: statInsight(player, "apg", 1) },
          { label: "SPG", value: formatNumber(player.spg, 1), insight: statInsight(player, "spg", 1) },
          { label: "BPG", value: formatNumber(player.bpg, 1), insight: statInsight(player, "bpg", 1) },
          { label: "TOPG", value: formatNumber(player.topg, 1), insight: statInsight(player, "topg", 1) },
          { label: "3P%", value: formatPct(player.threePct), insight: statInsight(player, "threePct", 1, true) },
          { label: "FG%", value: formatPct(player.fgPct), insight: statInsight(player, "fgPct", 1, true) },
          { label: "FT%", value: formatPct(player.ftPct), insight: statInsight(player, "ftPct", 1, true) },
          { label: "TS%", value: formatPct(player.tsPct), insight: statInsight(player, "tsPct", 1, true) },
          { label: "3P Rate", value: formatPct(player.threeRate), insight: statInsight(player, "threeRate", 1, true) },
          { label: "FT Rate", value: formatPct(player.ftRate), insight: statInsight(player, "ftRate", 1, true) },
          { label: "PTS/40", value: formatNumber(player.ptsPer40, 1), insight: statInsight(player, "ptsPer40", 1) },
          { label: "REB/40", value: formatNumber(player.rebPer40, 1), insight: statInsight(player, "rebPer40", 1) },
          { label: "AST/40", value: formatNumber(player.astPer40, 1), insight: statInsight(player, "astPer40", 1) },
          { label: "D2 Pwr", value: formatNumber(player.sourceConfPower, 2), insight: statInsight(player, "sourceConfPower", 2) },
          { label: "A/TO", value: formatRatio(player.apg, player.topg) },
          { label: "Team Pwr", value: formatNumber(player.sourceTeamPower, 2), insight: statInsight(player, "sourceTeamPower", 2) },
        ].map(renderStatCell).join("")}
      </div>
    </aside>
  `;
}

function renderPathways() {
  const former = selectedFormerPathwayPlayer();
  const similar = former ? similarCurrentPlayers(former) : [];
  const selectedCurrent =
    similar.find((player) => player.id === state.pathways.selectedCurrentId) ??
    null;

  return `
    <section class="view view-pathways">
      ${renderPageHeader({
        title: "Historical Comps",
        subtitle: "Pick a former D2 to D1 pathway, then inspect the closest current D2 players from the live pool.",
      })}
      ${renderPathwayControls(former)}
      <section class="projection-main-layout pathways-top-layout">
        ${former ? renderFormerDetail(former) : renderEmptyState("Pick a pathway", "Choose a former D2 to D1 player to load the former-player profile.")}
        <section class="content-card leaderboard-panel">
          <div class="section-block">
            <span class="section-label">Current D2 Matches</span>
            <h3>Closest present-day comps</h3>
            <p class="quality-note">Similarity uses workload, production, per-40 rates, TS%, 3P rate, FT rate, and conference/team context. Click a player to open the side-by-side comparison.</p>
          </div>
          <div class="table-wrap">
            <table class="data-table">
              <thead>
                <tr>
                  <th>Similarity</th>
                  <th>Current player</th>
                  <th>Team</th>
                  <th>Current D2 line</th>
                </tr>
              </thead>
              <tbody>
                ${similar.slice(0, 20).map((player) => {
                  return `
                  <tr class="${player.id === selectedCurrent?.id ? "selected" : ""}" data-current-comp-row="${escapeHtml(player.id)}">
                    <td><strong>${formatNumber(player.similarity, 0)}</strong></td>
                    <td><strong>${escapeHtml(player.name)}</strong><br /><span class="muted">${escapeHtml(player.position)} · ${escapeHtml(player.classYear)}</span></td>
                    <td>${escapeHtml(player.team)}<br /><span class="muted">${escapeHtml(player.conference)}</span></td>
                    <td>${formatNumber(player.ppg, 1)} PPG · ${formatNumber(player.rpg, 1)} RPG · ${formatNumber(player.apg, 1)} APG · ${formatNumber(player.games, 0)} GP</td>
                  </tr>
                `;}).join("")}
              </tbody>
            </table>
          </div>
        </section>
      </section>
    </section>
  `;
}

function renderPathwaysCurrentCard(player) {
  return `
    <article class="compare-card">
      <div class="compare-card-head">
        <span class="section-label">Current D2 player</span>
        <h3>${escapeHtml(player.name)}</h3>
        <p class="compare-subtitle">${escapeHtml(player.team)} · ${escapeHtml(player.conference)} · ${escapeHtml(player.position)} · ${escapeHtml(player.classYear)}</p>
      </div>
      <div class="compare-header">
        <div>
          <span class="mini-label">Current D2 profile</span>
          <div class="compare-value">${formatNumber(player.similarity, 0)}</div>
          <p class="quality-note">Similarity score against the selected historical comp</p>
        </div>
      </div>
      <div class="compare-stat-list">
        ${[
          ["GP", formatNumber(player.games, 0)],
          ["MPG", formatNumber(player.mpg, 1)],
          ["PPG", formatNumber(player.ppg, 1)],
          ["RPG", formatNumber(player.rpg, 1)],
          ["APG", formatNumber(player.apg, 1)],
          ["TS%", formatPct(player.tsPct)],
          ["3P Rate", formatPct(player.threeRate)],
          ["FT Rate", formatPct(player.ftRate)],
          ["PTS/40", formatNumber(player.ptsPer40, 1)],
          ["REB/40", formatNumber(player.rebPer40, 1)],
          ["AST/40", formatNumber(player.astPer40, 1)],
          ["3P%", formatPct(player.threePct)],
          ["D2 Pwr", formatNumber(player.sourceConfPower, 2)],
        ].map(([labelText, value]) => `<div class="compare-stat-item"><span>${labelText}</span><strong>${value}</strong></div>`).join("")}
      </div>
    </article>
  `;
}

function renderFormerDetail(player) {
  return `
    <article class="compare-card">
      <div class="compare-card-head">
        <span class="section-label">Historical comp</span>
        <h3>${escapeHtml(player.name)}</h3>
        <p class="compare-subtitle">${escapeHtml(player.sourceSchool)} to ${escapeHtml(player.destinationSchool)} · ${escapeHtml(player.firstD1Season)}</p>
      </div>
      <div class="compare-header">
        <div>
          <span class="mini-label">Actual ${escapeHtml(targetMeta().shortLabel)}</span>
          <div class="compare-value">${formatSigned(player.actualByTarget?.[state.target])}</div>
          <p class="quality-note">${escapeHtml(player.targetConference)} · ${escapeHtml(player.outcomeTier || "historical outcome")}</p>
        </div>
      </div>
      <div class="historical-compact-grid">
        <section class="historical-stat-panel">
          <span class="mini-label">Source D2 season</span>
          <div class="compare-stat-list">
            ${[
              ["GP", formatNumber(player.games, 0)],
              ["MPG", formatNumber(player.mpg, 1)],
              ["PPG", formatNumber(player.ppg, 1)],
              ["RPG", formatNumber(player.rpg, 1)],
              ["APG", formatNumber(player.apg, 1)],
              ["SPG", formatNumber(player.spg, 1)],
              ["BPG", formatNumber(player.bpg, 1)],
              ["TOPG", formatNumber(player.topg, 1)],
              ["FG%", formatPct(player.fgPct)],
              ["3P%", formatPct(player.threePct)],
              ["FT%", formatPct(player.ftPct)],
              ["TS%", formatPct(player.tsPct)],
              ["3P Rate", formatPct(player.threeRate)],
              ["FT Rate", formatPct(player.ftRate)],
              ["PTS/40", formatNumber(player.ptsPer40, 1)],
              ["REB/40", formatNumber(player.rebPer40, 1)],
              ["AST/40", formatNumber(player.astPer40, 1)],
              ["D2 Conf Pwr", formatNumber(player.sourceConfPower, 2)],
            ].map(([labelText, value]) => `<div class="compare-stat-item"><span>${labelText}</span><strong>${value}</strong></div>`).join("")}
          </div>
        </section>
        <section class="historical-stat-panel">
          <span class="mini-label">Eventual D1 outcome</span>
          <div class="compare-stat-list">
            ${[
              ["D1 GP", formatNumber(player.actualGames, 0)],
              ["D1 MPG", formatNumber(player.actualMpg, 1)],
              ["D1 PPG", formatNumber(player.actualPpg, 1)],
              ["D1 RPG", formatNumber(player.actualRpg, 1)],
              ["D1 APG", formatNumber(player.actualApg, 1)],
              ["Actual BPR", formatSigned(player.actualBpr)],
              ["Actual BPM", formatSigned(player.actualBpm)],
              ["Actual PORPAG", formatSigned(player.actualPorpag)],
              ["Actual Bart BPM", formatSigned(player.actualBarttorvikBpm)],
            ].map(([labelText, value]) => `<div class="compare-stat-item"><span>${labelText}</span><strong>${value}</strong></div>`).join("")}
          </div>
        </section>
      </div>
      <p class="quality-note">${player.sourceUrl ? `<a href="${escapeHtml(player.sourceUrl)}" target="_blank" rel="noreferrer">Source season</a>` : "No source season link"}${player.outcomeUrl ? ` · <a href="${escapeHtml(player.outcomeUrl)}" target="_blank" rel="noreferrer">First D1 season</a>` : ""}</p>
    </article>
  `;
}

function renderComparisonStatGrid(items) {
  return `
    <div class="comparison-stat-grid">
      ${items.map(([label, value]) => `
        <div class="comparison-stat-item">
          <span class="mini-label">${label}</span>
          <strong>${value}</strong>
        </div>
      `).join("")}
    </div>
  `;
}

function renderPathwayCompareOverlay() {
  if (state.route !== "pathways") return "";
  const former = selectedFormerPathwayPlayer();
  if (!former || !state.pathways.selectedCurrentId) return "";
  const similar = similarCurrentPlayers(former);
  const current = similar.find((player) => player.id === state.pathways.selectedCurrentId) ?? null;
  if (!current) return "";

  const formerStats = [
    ["D2 GP", formatNumber(former.games, 0)],
    ["D2 MPG", formatNumber(former.mpg, 1)],
    ["D2 PPG", formatNumber(former.ppg, 1)],
    ["D2 RPG", formatNumber(former.rpg, 1)],
    ["D2 APG", formatNumber(former.apg, 1)],
    ["D2 SPG", formatNumber(former.spg, 1)],
    ["D2 BPG", formatNumber(former.bpg, 1)],
    ["D2 TOPG", formatNumber(former.topg, 1)],
    ["D2 FG%", formatPct(former.fgPct)],
    ["D2 3P%", formatPct(former.threePct)],
    ["D2 FT%", formatPct(former.ftPct)],
    ["D2 eFG%", formatPct(former.efgPct)],
    ["D2 TS%", formatPct(former.tsPct)],
    ["D2 3P Rate", formatPct(former.threeRate)],
    ["D2 FT Rate", formatPct(former.ftRate)],
    ["D2 PTS/40", formatNumber(former.ptsPer40, 1)],
    ["D2 REB/40", formatNumber(former.rebPer40, 1)],
    ["D2 AST/40", formatNumber(former.astPer40, 1)],
    ["D2 STL/40", formatNumber(former.stlPer40, 1)],
    ["D2 BLK/40", formatNumber(former.blkPer40, 1)],
    ["D2 TOV/40", formatNumber(former.tovPer40, 1)],
    ["Actual D1 GP", formatNumber(former.actualGames, 0)],
    ["Actual D1 MPG", formatNumber(former.actualMpg, 1)],
    ["Actual D1 PPG", formatNumber(former.actualPpg, 1)],
  ];

  const currentStats = [
    ["GP", formatNumber(current.games, 0)],
    ["MPG", formatNumber(current.mpg, 1)],
    ["PPG", formatNumber(current.ppg, 1)],
    ["RPG", formatNumber(current.rpg, 1)],
    ["APG", formatNumber(current.apg, 1)],
    ["SPG", formatNumber(current.spg, 1)],
    ["BPG", formatNumber(current.bpg, 1)],
    ["TOPG", formatNumber(current.topg, 1)],
    ["FG%", formatPct(current.fgPct)],
    ["3P%", formatPct(current.threePct)],
    ["FT%", formatPct(current.ftPct)],
    ["eFG%", formatPct(current.efgPct)],
    ["TS%", formatPct(current.tsPct)],
    ["3P Rate", formatPct(current.threeRate)],
    ["FT Rate", formatPct(current.ftRate)],
    ["PTS/40", formatNumber(current.ptsPer40, 1)],
    ["REB/40", formatNumber(current.rebPer40, 1)],
    ["AST/40", formatNumber(current.astPer40, 1)],
    ["STL/40", formatNumber(current.stlPer40, 1)],
    ["BLK/40", formatNumber(current.blkPer40, 1)],
    ["TOV/40", formatNumber(current.tovPer40, 1)],
    ["Similarity", formatNumber(current.similarity, 0)],
    ["A/TO", formatRatio(current.apg, current.topg)],
  ];

  return `
    <div class="modal-shell compare-focus-shell" data-close-pathway-compare="true">
      <div class="compare-focus-modal" role="dialog" aria-modal="true" aria-label="Former and current player comparison">
        <div class="modal-head">
          <div>
            <span class="section-label">Side-by-side comparison</span>
            <h3>${escapeHtml(former.name)} vs ${escapeHtml(current.name)}</h3>
            <p class="compare-subtitle">Historical comp on the left, selected current D2 profile on the right.</p>
          </div>
          <button class="close-button" type="button" aria-label="Close comparison" data-close-pathway-compare="true">×</button>
        </div>
        <div class="compare-focus-grid">
          <article class="compare-focus-card">
            <div class="compare-card-head">
              <span class="section-label">Historical comp</span>
              <h3>${escapeHtml(former.name)}</h3>
              <p class="compare-subtitle">${escapeHtml(former.sourceSchool)} to ${escapeHtml(former.destinationSchool)} · ${escapeHtml(former.firstD1Season)}</p>
            </div>
            <div class="compare-header">
              <div>
                <span class="mini-label">Actual ${escapeHtml(targetMeta().shortLabel)}</span>
                <div class="compare-value">${formatSigned(former.actualByTarget?.[state.target])}</div>
                <p class="quality-note">${escapeHtml(former.targetConference)} · ${escapeHtml(former.outcomeTier || "historical outcome")}</p>
              </div>
            </div>
            ${renderComparisonStatGrid(formerStats)}
          </article>
          <article class="compare-focus-card">
            <div class="compare-card-head">
              <span class="section-label">Current D2 player</span>
              <h3>${escapeHtml(current.name)}</h3>
              <p class="compare-subtitle">${escapeHtml(current.team)} · ${escapeHtml(current.conference)} · ${escapeHtml(current.position)} · ${escapeHtml(current.classYear)}</p>
            </div>
            <div class="compare-header">
              <div>
                <span class="mini-label">Similarity score</span>
                <div class="compare-value">${formatNumber(current.similarity, 0)}</div>
                <p class="quality-note">Current D2 profile against the selected historical comp</p>
              </div>
            </div>
            ${renderComparisonStatGrid(currentStats)}
          </article>
        </div>
      </div>
    </div>
  `;
}

function renderRecruitingBoard() {
  const tiers = [
    {
      title: "Priority targets",
      filter: (player) => currentProjection(player).bpr >= 2.2,
      tone: "primary",
      copy: "Immediate high-end projection fits worth active evaluation.",
    },
    {
      title: "Rotation bets",
      filter: (player) => currentProjection(player).bpr >= 1.25 && currentProjection(player).bpr < 2.2,
      tone: "blue",
      copy: "Players who profile as plausible year-one contributors.",
    },
    {
      title: "Development swings",
      filter: (player) => currentProjection(player).bpr < 1.25,
      tone: "neutral",
      copy: "Longer-range or context-dependent bets to track, not force.",
    },
  ];

  return `
    <section class="view view-recruiting">
      <div>
        <h1 class="page-title">Recruiting Board</h1>
        <p class="page-subtitle">Organize the player pool into simple roster-building tiers based on the selected projection target in the current destination context.</p>
      </div>
      ${renderDestinationContextControls({ title: "Board context" })}
      <section class="board-grid">
        ${tiers.map((tier) => {
          const players = sortPlayers(filteredPlayers().filter(tier.filter), "bpr").slice(0, 8);
          return `
            <article class="board-card">
              <span class="badge ${tier.tone}">${escapeHtml(tier.title)}</span>
              <p>${escapeHtml(tier.copy)}</p>
              <div class="board-player-list">
                ${players.map((player) => `<div><span>${escapeHtml(player.name)}<br /><span class="muted">${formatPct(player.tsPct)} TS · ${formatPct(player.threeRate)} 3P rate · ${formatNumber(player.games, 0)} GP</span></span><strong>${formatSigned(currentProjection(player).bpr)}</strong></div>`).join("") || `<div><span>No players</span><strong>-</strong></div>`}
              </div>
            </article>
          `;
        }).join("")}
      </section>
    </section>
  `;
}

function renderMethodology() {
  const targets = targetOptions();
  return `
    <section class="view view-methodology">
      ${renderPageHeader({
        title: "Methodology (in progress)",
        subtitle: "How the D2 Player Dashboard builds projections, raw-stat context, and historical similarity matches.",
      })}
      <section class="methodology-grid">
        <article class="content-card">
          <span class="section-label">Projection model</span>
          <h3>Current approach</h3>
          <p class="quality-note">${escapeHtml(state.data?.meta?.note ?? "")}</p>
          <div class="methodology-target-list">
            ${targets.map(([key, meta]) => `
              <div class="methodology-target-item">
                <div>
                  <strong>${escapeHtml(targetOptionLabel(key, meta))}</strong>
                  <p class="quality-note">${escapeHtml(meta.model)} · ${escapeHtml(meta.family)}</p>
                </div>
                <div class="methodology-metrics">
                  <span>Rows ${formatInteger(meta.rowsUsed)}</span>
                  <span>R² ${formatNumber(meta.cvR2, 3)}</span>
                  <span>Corr ${formatNumber(meta.cvCorr, 3)}</span>
                </div>
              </div>
            `).join("")}
          </div>
        </article>
        <article class="content-card">
          <span class="section-label">Similarity</span>
          <h3>Historical comps</h3>
          <p class="quality-note">Similarity is a weighted z-score comparison across workload, per-game production, per-40 rates, shooting efficiency, 3P rate, FT rate, and conference/team context. It does not use PCA right now.</p>
          <p class="quality-note">Historical comps let you start from a former D2-to-D1 pathway and then inspect the closest current D2 profiles.</p>
        </article>
        <article class="content-card">
          <span class="section-label">Raw stats context</span>
          <h3>Percentiles and above average</h3>
          <p class="quality-note">For current D2 players, the detail views now show percentile rank and above/below-average context versus the full current tracked D2 pool for each displayed stat.</p>
        </article>
        <article class="content-card">
          <span class="section-label">To Do</span>
          <h3>Known next steps</h3>
          <ul class="methodology-list">
            <li>Rework RAPM targets if the range remains too compressed relative to basketball intuition.</li>
            <li>Bring back the verification/data-quality layer after the UI is stabilized, with clearer sourcing and missing-stat explanations.</li>
            <li>Keep expanding historical transfer coverage beyond the current target-conference focus.</li>
          </ul>
        </article>
      </section>
    </section>
  `;
}

function findPlayer(id) {
  return state.players.find((player) => player.id === id) ?? null;
}

function renderPlayerModal() {
  const player = findPlayer(state.modal.playerId);
  if (!player) return "";
  const projection = currentProjection(player);
  return `
    <div class="modal-shell" data-close-player-modal="true">
      <div class="modal-card" role="dialog" aria-modal="true" aria-label="Player similarity card">
        <div class="modal-head">
          <div>
            <span class="section-label">${escapeHtml(player.team)} · ${escapeHtml(player.conference)}</span>
            <h3>${escapeHtml(player.name)}</h3>
            <p class="compare-subtitle">${escapeHtml(player.position)} · ${escapeHtml(player.heightLabel)} · ${escapeHtml(player.classYear)}</p>
          </div>
          <button class="close-button" type="button" aria-label="Close" data-close-player-modal="true">×</button>
        </div>
        <div class="score-card">
          <span class="section-label">Current scenario</span>
          <strong>${projection ? formatSigned(projection.bpr) : "-"}</strong>
          <p>${projection ? `${escapeHtml(projection.schoolName ?? "-")} · ${formatNumber(projection.projectedMpg, 0)} MPG` : "Projection unavailable"}</p>
        </div>
        <div class="detail-stat-grid">
          ${[
            ["GP", formatNumber(player.games, 0)],
            ["MPG", formatNumber(player.mpg, 1)],
            ["PPG", formatNumber(player.ppg, 1)],
            ["RPG", formatNumber(player.rpg, 1)],
            ["APG", formatNumber(player.apg, 1)],
            ["TS%", formatPct(player.tsPct)],
            ["3P Rate", formatPct(player.threeRate)],
            ["FT Rate", formatPct(player.ftRate)],
            ["3P%", formatPct(player.threePct)],
            ["PTS/40", formatNumber(player.ptsPer40, 1)],
            ["AST/40", formatNumber(player.astPer40, 1)],
            [targetMeta().shortLabel, projection ? formatSigned(projection.bpr) : "-"],
          ].map(([label, value]) => `<div><span class="mini-label">${label}</span><strong>${value}</strong></div>`).join("")}
        </div>
      </div>
    </div>
  `;
}

function renderView() {
  switch (state.route) {
    case "leaderboard":
      return renderLeaderboard();
    case "raw-stats":
      return renderRawStats();
    case "pathways":
      return renderPathways();
    case "methodology":
      return renderMethodology();
    case "recruiting-board":
      return renderRecruitingBoard();
    default:
      return renderLeaderboard();
  }
}

function syncNav() {
  els.navList.querySelectorAll(".nav-link").forEach((link) => {
    link.classList.toggle("active", link.dataset.route === state.route);
  });
}

function setNavOpen(open) {
  state.navOpen = open;
  els.sidebar.classList.toggle("open", open);
  els.navOverlay.hidden = !open;
  els.menuToggle.setAttribute("aria-expanded", String(open));
}

function render() {
  els.viewRoot.innerHTML = `${renderView()}${renderPathwayCompareOverlay()}${renderPlayerModal()}`;
  syncNav();
  hydrateViewControls();
}

function hydrateViewControls() {
  const targetPicker = document.querySelector("#targetPicker");
  if (targetPicker) {
    targetPicker.value = state.target;
    targetPicker.addEventListener("change", (event) => {
      state.target = event.target.value;
      state.search.minBpr = projectionFilterOptions()[0];
      render();
    });
  }

  const destinationPicker = document.querySelector("#destinationPicker");
  if (destinationPicker) {
    destinationPicker.value = state.destination;
    destinationPicker.addEventListener("change", (event) => {
      state.destination = event.target.value;
      state.destinationSchoolByConference[state.destination] = selectedDestinationSchool(state.destination);
      state.projectedMpgByConference[state.destination] = selectedProjectedMpg(state.destination);
      render();
    });
  }

  const destinationSchoolPicker = document.querySelector("#destinationSchoolPicker");
  if (destinationSchoolPicker) {
    destinationSchoolPicker.value = selectedDestinationSchool(state.destination);
    destinationSchoolPicker.addEventListener("change", (event) => {
      const school = schoolContext(state.destination, event.target.value);
      state.destinationSchoolByConference[state.destination] = school?.slug ?? defaultDestinationSchool(state.destination);
      state.projectedMpgByConference[state.destination] = school?.defaultProjectedMpg ?? minuteScenarioOptions()[0];
      render();
    });
  }

  const projectedMpgRange = document.querySelector("#projectedMpgRange");
  if (projectedMpgRange) {
    projectedMpgRange.value = String(selectedProjectedMpg(state.destination));
    projectedMpgRange.addEventListener("input", (event) => {
      state.projectedMpgByConference[state.destination] = Number(event.target.value);
      render();
    });
  }

  document.querySelectorAll("[data-player-row]").forEach((row) => {
    row.addEventListener("click", () => {
      state.leaderboard.selectedId = row.dataset.playerRow;
      render();
    });
  });

  document.querySelectorAll("[data-raw-player-row]").forEach((row) => {
    row.addEventListener("click", () => {
      state.rawStats.selectedId = row.dataset.rawPlayerRow;
      render();
    });
  });

  document.querySelectorAll("[data-current-comp-row]").forEach((row) => {
    row.addEventListener("click", () => {
      state.pathways.selectedCurrentId = row.dataset.currentCompRow;
      render();
    });
  });

  document.querySelectorAll("[data-destination]").forEach((button) => {
    button.addEventListener("click", () => {
      state.destination = button.dataset.destination;
      render();
    });
  });

  document.querySelectorAll("[data-sort]").forEach((button) => {
    button.addEventListener("click", () => {
      state.leaderboard.sort = button.dataset.sort;
      render();
    });
  });

  document.querySelectorAll("[data-raw-sort]").forEach((button) => {
    button.addEventListener("click", () => {
      state.rawStats.sort = button.dataset.rawSort;
      render();
    });
  });

  const searchQuery = document.querySelector("#searchQuery");
  if (searchQuery) {
    searchQuery.addEventListener("input", (event) => {
      state.search.query = event.target.value;
      render();
    });
  }

  [
    ["#searchClass", "classYear"],
    ["#searchConference", "conference"],
    ["#searchPosition", "position"],
    ["#searchMinBpr", "minBpr"],
  ].forEach(([selector, key]) => {
    const element = document.querySelector(selector);
    if (!element) return;
    element.addEventListener("change", (event) => {
      state.search[key] = key === "minBpr" ? Number(event.target.value) : event.target.value;
      render();
    });
  });

  const resetSearch = document.querySelector("#resetSearch");
  if (resetSearch) {
    resetSearch.addEventListener("click", () => {
      state.search = {
        query: "",
        classYear: "All",
        conference: "All",
        position: "All",
        minBpr: -2,
      };
      render();
    });
  }

  const pathwayFormerPlayer = document.querySelector("#pathwayFormerPlayer");
  if (pathwayFormerPlayer) {
    pathwayFormerPlayer.value = state.pathways.formerId ?? "";
    pathwayFormerPlayer.addEventListener("change", (event) => {
      state.pathways.formerId = event.target.value || null;
      state.pathways.selectedCurrentId = null;
      render();
    });
  }

  const leaderboardPlayerPicker = document.querySelector("#leaderboardPlayerPicker");
  if (leaderboardPlayerPicker) {
    leaderboardPlayerPicker.addEventListener("change", (event) => {
      state.leaderboard.selectedId = event.target.value || null;
      render();
    });
  }

  document.querySelectorAll("[data-open-player-modal]").forEach((button) => {
    button.addEventListener("click", () => {
      state.modal.playerId = button.dataset.openPlayerModal;
      render();
    });
  });

  document.querySelectorAll("[data-close-player-modal]").forEach((element) => {
    element.addEventListener("click", (event) => {
      if (element.classList.contains("modal-shell") && event.target !== element) return;
      state.modal.playerId = null;
      render();
    });
  });

  document.querySelectorAll("[data-close-pathway-compare]").forEach((element) => {
    element.addEventListener("click", (event) => {
      if (element.classList.contains("modal-shell") && event.target !== element) return;
      state.pathways.selectedCurrentId = null;
      render();
    });
  });
}

function bindChromeEvents() {
  els.menuToggle.addEventListener("click", () => setNavOpen(true));
  els.menuClose.addEventListener("click", () => setNavOpen(false));
  els.navOverlay.addEventListener("click", () => setNavOpen(false));
  els.quickCompare.addEventListener("click", () => {
    location.hash = "#pathways";
  });
  window.addEventListener("hashchange", () => {
    state.route = normalizeRoute(location.hash);
    setNavOpen(false);
    render();
  });
}

async function initialize() {
  els.viewRoot.innerHTML = renderLoadingState();
  const response = await fetch(DATA_URL);
  if (!response.ok) throw new Error(`Could not load projection data: ${response.status}`);
  state.data = await response.json();
  state.players = state.data.players;
  state.formerPlayers = state.data.formerD2Players ?? [];
  if (!state.formerPlayers.length) {
    state.formerPlayers = await loadFormerPlayersFallback();
  }
  state.benchmarks = buildBenchmarks(state.players);
  state.target = state.data.meta.defaultTarget ?? "bpr";
  state.data.meta.conferences.forEach((conference) => {
    const school = defaultDestinationSchool(conference);
    state.destinationSchoolByConference[conference] = school;
    state.projectedMpgByConference[conference] = schoolContext(conference, school)?.defaultProjectedMpg ?? minuteScenarioOptions()[0];
  });
  state.route = normalizeRoute(location.hash);
  state.leaderboard.selectedId = sortPlayers(state.players, "bpr")[0]?.id ?? null;
  state.rawStats.selectedId = sortRawPlayers(state.players, "ppg")[0]?.id ?? null;
  state.pathways.formerId = sortedFormerPlayers()[0]?.id ?? null;
  state.pathways.selectedCurrentId = null;
  bindChromeEvents();
  render();
}

initialize().catch((error) => {
  console.error(error);
  els.viewRoot.innerHTML = renderEmptyState("Could not load projection data.", "Check the JSON build output and refresh the page.");
});
