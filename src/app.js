const DATA_URL = "./data/projection_dashboard_data.json";
const DEFAULT_DESTINATION = "Big West";
const DEFAULT_ROUTE = "leaderboard";

const ROUTES = [
  "leaderboard",
  "compare",
  "recruiting-board",
];

const state = {
  data: null,
  players: [],
  route: DEFAULT_ROUTE,
  destination: DEFAULT_DESTINATION,
  target: "bpr",
  destinationSchoolByConference: {},
  projectedMpgByConference: {},
  navOpen: false,
  compareIds: [null, null],
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
};

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

function targetOptions() {
  return Object.entries(state.data?.meta?.projectionTargets ?? {});
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

function filteredPlayers() {
  const query = state.search.query.trim().toLowerCase();
  return state.players.filter((player) => {
    const projection = currentProjection(player);
    if (!projection) return false;
    if (query) {
      const haystack = `${player.name} ${player.team} ${player.conference} ${player.position}`.toLowerCase();
      if (!haystack.includes(query)) return false;
    }
    if (state.search.classYear !== "All" && player.classYear !== state.search.classYear) return false;
    if (state.search.conference !== "All" && player.conference !== state.search.conference) return false;
    if (state.search.position !== "All" && player.position !== state.search.position) return false;
    if (projection.bpr < state.search.minBpr) return false;
    return true;
  });
}

function sortPlayers(players, key = "bpr") {
  const copy = [...players];
  copy.sort((a, b) => {
    if (key === "name") return a.name.localeCompare(b.name);
    if (key === "ppg") return b.ppg - a.ppg;
    if (key === "mpg") return b.mpg - a.mpg;
    if (key === "verified") return Number(b.verifiedCurrentStats) - Number(a.verifiedCurrentStats);
    return currentProjection(b).bpr - currentProjection(a).bpr;
  });
  return copy;
}

function topPlayers(limit = 6) {
  return sortPlayers(filteredPlayers(), "bpr").slice(0, limit);
}

function qualityBadge(player) {
  if (player.verifiedCurrentStats) return `<span class="badge green">Verified</span>`;
  if (player.eventStatsFlagged) return `<span class="badge gold">Flagged</span>`;
  return `<span class="badge neutral">Unverified</span>`;
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
            ${targetOptions().map(([key, meta]) => `<option value="${escapeHtml(key)}" ${key === target ? "selected" : ""}>${escapeHtml(meta.label)}</option>`).join("")}
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
          ${qualityBadge(player)}
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

function searchToolbar() {
  const classYears = ["All", ...uniqueSorted(state.players.map((player) => player.classYear))];
  const conferences = ["All", ...uniqueSorted(state.players.map((player) => player.conference))];
  const positions = ["All", ...uniqueSorted(state.players.map((player) => player.position))];

  return `
    <section class="content-card">
      <div class="toolbar">
        <div class="toolbar-left">
          <input id="searchQuery" class="search-input" type="search" placeholder="Search player, team, conference, or position" value="${escapeHtml(state.search.query)}" />
        </div>
        <div class="toolbar-right">
          <button id="resetSearch" class="pill-button" type="button">Reset filters</button>
        </div>
      </div>
      <div class="filter-grid">
        ${renderSelect("searchClass", classYears, state.search.classYear)}
        ${renderSelect("searchConference", conferences, state.search.conference)}
        ${renderSelect("searchPosition", positions, state.search.position)}
        <label>
          <span class="mini-label">Min ${escapeHtml(targetMeta().shortLabel)}</span>
          <select id="searchMinBpr" class="select-input">
            ${projectionFilterOptions().map((value) => `<option value="${value}" ${Number(value) === Number(state.search.minBpr) ? "selected" : ""}>${value}</option>`).join("")}
          </select>
        </label>
      </div>
    </section>
  `;
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

function renderLeaderboard() {
  const players = sortPlayers(filteredPlayers(), state.leaderboard.sort);
  const selected = players.find((player) => player.id === state.leaderboard.selectedId) ?? players[0] ?? null;
  if (selected && !state.leaderboard.selectedId) state.leaderboard.selectedId = selected.id;

  return `
    <section class="view">
      <div>
        <h1 class="page-title">Leaderboard</h1>
        <p class="page-subtitle">Ranked ${escapeHtml(targetMeta().shortLabel)} projections in the current destination-team context, with player detail and fit breakdown.</p>
      </div>
      ${summaryStats()}
      <section class="content-card">
        <div class="toolbar">
          <div class="toolbar-left">
            <button class="tab-button ${state.leaderboard.sort === "bpr" ? "active" : ""}" type="button" data-sort="bpr">Proj. ${escapeHtml(targetMeta().shortLabel)}</button>
            <button class="tab-button ${state.leaderboard.sort === "ppg" ? "active" : ""}" type="button" data-sort="ppg">PPG</button>
            <button class="tab-button ${state.leaderboard.sort === "mpg" ? "active" : ""}" type="button" data-sort="mpg">MPG</button>
            <button class="tab-button ${state.leaderboard.sort === "name" ? "active" : ""}" type="button" data-sort="name">Name</button>
            <button class="tab-button ${state.leaderboard.sort === "verified" ? "active" : ""}" type="button" data-sort="verified">Verified</button>
          </div>
        </div>
      </section>
      ${renderDestinationContextControls({ title: "Leaderboard scenario" })}
      ${searchToolbar()}
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
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              ${players.slice(0, 150).map((player, index) => renderLeaderboardRow(player, index, selected?.id)).join("")}
            </tbody>
          </table>
        </div>
        ${selected ? renderLeaderDetail(selected) : renderEmptyState("No player selected.", "Choose a player from the leaderboard to inspect their profile.")}
      </section>
    </section>
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
      <td>${qualityBadge(player)}</td>
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
          ["Going to", escapeHtml(projection.schoolName ?? "-")],
          ["GP", formatNumber(player.games, 0)],
          ["PPG", formatNumber(player.ppg, 1)],
          ["RPG", formatNumber(player.rpg, 1)],
          ["APG", formatNumber(player.apg, 1)],
          ["PTS/40", formatNumber(player.ptsPer40, 1)],
          ["REB/40", formatNumber(player.rebPer40, 1)],
          ["AST/40", formatNumber(player.astPer40, 1)],
          ["3P%", formatPct(player.threePct)],
          ["eFG%", formatPct(player.efgPct)],
          ["D2 Pwr", formatNumber(player.sourceConfPower, 2)],
          ["Dest Team Pwr", formatNumber(projection.destinationTeamPower, 2)],
          [targetMeta().shortLabel, formatSigned(projection.bpr)],
        ].map(([label, value]) => `<div><span class="mini-label">${label}</span><strong>${value}</strong></div>`).join("")}
      </div>
      <div class="content-card">
        <span class="mini-label">Data quality</span>
        ${qualityBadge(player)}
        <p class="quality-note">${player.verifiedSourceUrl ? `<a href="${escapeHtml(player.verifiedSourceUrl)}" target="_blank" rel="noreferrer">Open verified source</a>` : "No verified source URL attached yet."}</p>
      </div>
    </aside>
  `;
}

function renderCompare() {
  const options = state.players
    .slice(0, 500)
    .map((player) => `<option value="${escapeHtml(player.id)}">${escapeHtml(player.name)} · ${escapeHtml(player.team)}</option>`)
    .join("");
  const left = findPlayer(state.compareIds[0]) ?? sortPlayers(state.players, "bpr")[0] ?? null;
  const right = findPlayer(state.compareIds[1]) ?? sortPlayers(state.players, "bpr")[1] ?? null;

  return `
    <section class="view">
      <div>
        <h1 class="page-title">Compare</h1>
        <p class="page-subtitle">Select two prospects and compare their D2 production, projected ${escapeHtml(targetMeta().shortLabel)}, and destination-team fit side by side.</p>
      </div>
      ${renderDestinationContextControls({ title: "Compare context" })}
      <section class="content-card">
        <div class="compare-selects">
          <select id="compareLeft" class="select-input">
            <option value="">Select first player</option>
            ${options}
          </select>
          <select id="compareRight" class="select-input">
            <option value="">Select second player</option>
            ${options}
          </select>
        </div>
      </section>
      <section class="compare-grid">
        ${left ? renderCompareCard(left, "Left") : renderEmptyState("Pick a player", "Use the selector above to start a comparison.")}
        ${right ? renderCompareCard(right, "Right") : renderEmptyState("Pick a player", "Use the selector above to start a comparison.")}
      </section>
    </section>
  `;
}

function renderCompareCard(player, label) {
  const projection = currentProjection(player);
  const bestFit = projectionEntries(player)[0];
  const school = schoolContext(state.destination, selectedDestinationSchool(state.destination));
  return `
    <article class="compare-card">
      <div class="compare-card-head">
        <span class="section-label">${escapeHtml(label)} player</span>
        <h3>${escapeHtml(player.name)}</h3>
        <p class="compare-subtitle">${escapeHtml(player.team)} · ${escapeHtml(player.position)} · ${escapeHtml(player.classYear)}</p>
      </div>
      <div class="compare-header">
        <div>
          <span class="mini-label">Projected ${escapeHtml(targetMeta().shortLabel)}</span>
          <div class="compare-value">${formatSigned(projection.bpr)}</div>
          <p class="quality-note">${escapeHtml(school?.name ?? state.destination)} · ${formatNumber(projection.projectedMpg, 0)} MPG</p>
        </div>
        ${qualityBadge(player)}
      </div>
      <div class="compare-stat-list">
        ${[
          ["Going to", escapeHtml(projection.schoolName ?? "-")],
          ["GP", formatNumber(player.games, 0)],
          ["PPG", formatNumber(player.ppg, 1)],
          ["MPG", formatNumber(player.mpg, 1)],
          ["RPG", formatNumber(player.rpg, 1)],
          ["APG", formatNumber(player.apg, 1)],
          ["3P%", formatPct(player.threePct)],
          ["PTS/40", formatNumber(player.ptsPer40, 1)],
          ["Best fit", escapeHtml(bestFit?.[0] ?? "-")],
          [`Best ${targetMeta().shortLabel}`, formatSigned(bestFit?.[1]?.bpr)],
        ].map(([labelText, value]) => `<div class="compare-stat-item"><span>${labelText}</span><strong>${value}</strong></div>`).join("")}
      </div>
    </article>
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
    <section class="view">
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
                ${players.map((player) => `<div><span>${escapeHtml(player.name)}</span><strong>${formatSigned(currentProjection(player).bpr)}</strong></div>`).join("") || `<div><span>No players</span><strong>-</strong></div>`}
              </div>
            </article>
          `;
        }).join("")}
      </section>
    </section>
  `;
}

function findPlayer(id) {
  return state.players.find((player) => player.id === id) ?? null;
}

function renderView() {
  switch (state.route) {
    case "leaderboard":
      return renderLeaderboard();
    case "compare":
      return renderCompare();
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
  els.viewRoot.innerHTML = renderView();
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

  const compareLeft = document.querySelector("#compareLeft");
  const compareRight = document.querySelector("#compareRight");
  if (compareLeft) {
    compareLeft.value = state.compareIds[0] ?? "";
    compareLeft.addEventListener("change", (event) => {
      state.compareIds[0] = event.target.value || null;
      render();
    });
  }
  if (compareRight) {
    compareRight.value = state.compareIds[1] ?? "";
    compareRight.addEventListener("change", (event) => {
      state.compareIds[1] = event.target.value || null;
      render();
    });
  }

}

function bindChromeEvents() {
  els.menuToggle.addEventListener("click", () => setNavOpen(true));
  els.menuClose.addEventListener("click", () => setNavOpen(false));
  els.navOverlay.addEventListener("click", () => setNavOpen(false));
  els.quickCompare.addEventListener("click", () => {
    location.hash = "#compare";
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
  state.target = state.data.meta.defaultTarget ?? "bpr";
  state.data.meta.conferences.forEach((conference) => {
    const school = defaultDestinationSchool(conference);
    state.destinationSchoolByConference[conference] = school;
    state.projectedMpgByConference[conference] = schoolContext(conference, school)?.defaultProjectedMpg ?? minuteScenarioOptions()[0];
  });
  state.route = normalizeRoute(location.hash);
  state.compareIds = [
    sortPlayers(state.players, "bpr")[0]?.id ?? null,
    sortPlayers(state.players, "bpr")[1]?.id ?? null,
  ];
  state.leaderboard.selectedId = sortPlayers(state.players, "bpr")[0]?.id ?? null;
  bindChromeEvents();
  render();
}

initialize().catch((error) => {
  console.error(error);
  els.viewRoot.innerHTML = renderEmptyState("Could not load projection data.", "Check the JSON build output and refresh the page.");
});
