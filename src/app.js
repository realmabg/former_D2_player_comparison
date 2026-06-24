const DATA_URL = "./data/projection_dashboard_data.json";

const DEFAULT_DESTINATION = "Big West";

const DEFAULT_FILTERS = {
  search: "",
  classYear: "All",
  sourceConference: "All",
  position: "All",
  minBpr: -2,
  minMpg: 0,
  minPpg: 0,
  sort: "projected",
};

const state = {
  data: null,
  players: [],
  selectedId: null,
  destination: DEFAULT_DESTINATION,
  filters: { ...DEFAULT_FILTERS },
};

const els = {
  modelMeta: document.querySelector("#modelMeta"),
  rowsUsed: document.querySelector("#rowsUsed"),
  cvR2: document.querySelector("#cvR2"),
  cvCorr: document.querySelector("#cvCorr"),
  cvMae: document.querySelector("#cvMae"),
  visiblePlayers: document.querySelector("#visiblePlayers"),
  verifiedPlayers: document.querySelector("#verifiedPlayers"),
  flaggedPlayers: document.querySelector("#flaggedPlayers"),
  topProjection: document.querySelector("#topProjection"),
  topProjectionLabel: document.querySelector("#topProjectionLabel"),
  boardSubtitle: document.querySelector("#boardSubtitle"),
  searchInput: document.querySelector("#searchInput"),
  destinationFilter: document.querySelector("#destinationFilter"),
  classFilter: document.querySelector("#classFilter"),
  sourceConferenceFilter: document.querySelector("#sourceConferenceFilter"),
  positionFilter: document.querySelector("#positionFilter"),
  minBpr: document.querySelector("#minBpr"),
  minMpg: document.querySelector("#minMpg"),
  minPpg: document.querySelector("#minPpg"),
  minBprValue: document.querySelector("#minBprValue"),
  minMpgValue: document.querySelector("#minMpgValue"),
  minPpgValue: document.querySelector("#minPpgValue"),
  sortSelect: document.querySelector("#sortSelect"),
  conferenceTabs: document.querySelector("#conferenceTabs"),
  playerRows: document.querySelector("#playerRows"),
  resultCount: document.querySelector("#resultCount"),
  playerDetail: document.querySelector("#playerDetail"),
  boardTitle: document.querySelector("#boardTitle"),
  resetFilters: document.querySelector("#resetFilters"),
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

function formatPct(value) {
  const number = Number(value);
  return Number.isFinite(number) ? `${Math.round(number * 100)}%` : "-";
}

function formatInteger(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number.toLocaleString() : "-";
}

function uniqueSorted(values) {
  return [...new Set(values.filter(Boolean))].sort((a, b) => String(a).localeCompare(String(b)));
}

function currentProjection(player) {
  return player.projections[state.destination] ?? player.projections[player.bestConference];
}

function searchText(player) {
  return `${player.name} ${player.team} ${player.conference} ${player.position}`.toLowerCase();
}

function playerScore(player) {
  const projection = currentProjection(player);
  switch (state.filters.sort) {
    case "ppg":
      return player.ppg;
    case "mpg":
      return player.mpg;
    case "ptsPer40":
      return player.ptsPer40;
    case "astPer40":
      return player.astPer40;
    case "rebPer40":
      return player.rebPer40;
    case "sourcePower":
      return player.sourceConfPower ?? -99;
    default:
      return projection.bpr;
  }
}

function filteredPlayers() {
  const text = state.filters.search.trim().toLowerCase();
  return state.players
    .filter((player) => {
      const projection = currentProjection(player);
      if (text && !searchText(player).includes(text)) return false;
      if (state.filters.classYear !== "All" && player.classYear !== state.filters.classYear) return false;
      if (state.filters.sourceConference !== "All" && player.conference !== state.filters.sourceConference) return false;
      if (state.filters.position !== "All" && player.position !== state.filters.position) return false;
      if (projection.bpr < state.filters.minBpr) return false;
      if (player.mpg < state.filters.minMpg) return false;
      if (player.ppg < state.filters.minPpg) return false;
      return true;
    })
    .sort((a, b) => {
      const scoreDiff = playerScore(b) - playerScore(a);
      if (scoreDiff !== 0) return scoreDiff;
      return a.name.localeCompare(b.name);
    });
}

function renderOptions(select, values, selected) {
  select.innerHTML = values
    .map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`)
    .join("");
  select.value = selected;
}

function renderFilters() {
  const conferences = state.data.meta.conferences;
  renderOptions(els.destinationFilter, conferences, state.destination);
  renderOptions(els.classFilter, ["All", ...uniqueSorted(state.players.map((player) => player.classYear))], state.filters.classYear);
  renderOptions(
    els.sourceConferenceFilter,
    ["All", ...uniqueSorted(state.players.map((player) => player.conference))],
    state.filters.sourceConference,
  );
  renderOptions(
    els.positionFilter,
    ["All", ...uniqueSorted(state.players.map((player) => player.position))],
    state.filters.position,
  );
}

function renderTabs() {
  els.conferenceTabs.innerHTML = state.data.meta.conferences
    .map((conference) => {
      const active = conference === state.destination ? "active" : "";
      return `<button class="${active}" type="button" data-conference="${escapeHtml(conference)}">${escapeHtml(conference)}</button>`;
    })
    .join("");
}

function renderMeta() {
  const meta = state.data.meta;
  els.modelMeta.textContent = `${meta.model} | ${meta.target}`;
  els.rowsUsed.textContent = meta.rowsUsed;
  els.cvR2.textContent = formatNumber(meta.cvR2, 3);
  els.cvCorr.textContent = formatNumber(meta.cvCorr, 3);
  els.cvMae.textContent = formatNumber(meta.cvMae, 3);
  els.boardTitle.textContent = `${state.destination} projection board`;
  els.boardSubtitle.textContent =
    "Conference tabs re-score the same player pool against a different destination context, so you can scan fit instead of staring at one static rank order.";
}

function qualityState(player) {
  if (player.verifiedCurrentStats) return { className: "verified", label: "Verified" };
  if (player.eventStatsFlagged) return { className: "flagged", label: "Flagged" };
  return { className: "unverified", label: "Unverified" };
}

function renderRows(players) {
  const visible = players.slice(0, 150);
  els.resultCount.textContent = `${players.length.toLocaleString()} players`;
  els.playerRows.innerHTML = visible
    .map((player, index) => {
      const projection = currentProjection(player);
      const selected = player.id === state.selectedId ? "selected" : "";
      const quality = qualityState(player);
      return `
        <tr class="${selected}" data-player-id="${escapeHtml(player.id)}">
          <td>
            <div class="player-cell">
              <span class="rank">${index + 1}</span>
              <div>
                <strong>${escapeHtml(player.name)}</strong>
                <span>${escapeHtml(player.team)} | ${escapeHtml(player.conference)}</span>
              </div>
            </div>
          </td>
          <td>${escapeHtml(state.destination)}</td>
          <td><strong class="bpr">${formatNumber(projection.bpr, 2)}</strong><span class="tier">${escapeHtml(projection.tier)}</span></td>
          <td>${formatNumber(player.mpg, 1)}</td>
          <td>${formatNumber(player.ppg, 1)}</td>
          <td>${formatNumber(player.ptsPer40, 1)} / ${formatNumber(player.rebPer40, 1)} / ${formatNumber(player.astPer40, 1)}</td>
          <td>
            <div class="quality-cell">
              <strong>${escapeHtml(player.position)} | ${escapeHtml(player.heightLabel)} | ${escapeHtml(player.classYear)}</strong>
              <span class="quality-badge ${quality.className}">${quality.label}</span>
              <span class="quality-note">${escapeHtml(player.bestConference)} best fit</span>
            </div>
          </td>
        </tr>
      `;
    })
    .join("");
}

function projectionBars(player) {
  const entries = Object.entries(player.projections).sort((a, b) => b[1].bpr - a[1].bpr);
  const values = entries.map(([, projection]) => projection.bpr);
  const min = Math.min(-2, ...values);
  const max = Math.max(6, ...values);
  return entries
    .map(([conference, projection]) => {
      const width = ((projection.bpr - min) / (max - min)) * 100;
      const active = conference === state.destination ? "active" : "";
      return `
        <button class="projection-row ${active}" type="button" data-conference="${escapeHtml(conference)}">
          <span>${escapeHtml(conference)}</span>
          <strong>${formatNumber(projection.bpr, 2)}</strong>
          <i style="width:${width}%"></i>
        </button>
      `;
    })
    .join("");
}

function statGrid(player) {
  const stats = [
    ["MPG", formatNumber(player.mpg, 1)],
    ["PPG", formatNumber(player.ppg, 1)],
    ["RPG", formatNumber(player.rpg, 1)],
    ["APG", formatNumber(player.apg, 1)],
    ["PTS/40", formatNumber(player.ptsPer40, 1)],
    ["REB/40", formatNumber(player.rebPer40, 1)],
    ["AST/40", formatNumber(player.astPer40, 1)],
    ["STL/40", formatNumber(player.stlPer40, 1)],
    ["3P%", formatPct(player.threePct)],
    ["eFG", formatPct(player.efgPct)],
    ["3PA/FGA", formatPct(player.threeRate)],
    ["D2 Pwr", formatNumber(player.sourceConfPower, 2)],
  ];
  return stats.map(([label, value]) => `<div><span>${label}</span><strong>${value}</strong></div>`).join("");
}

function projectionSummary(player) {
  const entries = Object.entries(player.projections).sort((a, b) => b[1].bpr - a[1].bpr);
  const best = entries[0];
  const worst = entries.at(-1);
  return {
    bestConference: best?.[0] ?? "-",
    bestBpr: best?.[1]?.bpr ?? null,
    worstConference: worst?.[0] ?? "-",
    worstBpr: worst?.[1]?.bpr ?? null,
  };
}

function renderDetail(players) {
  const selected = state.players.find((player) => player.id === state.selectedId) ?? players[0] ?? state.players[0];
  if (!selected) {
    els.playerDetail.innerHTML = "";
    return;
  }
  state.selectedId = selected.id;
  const projection = currentProjection(selected);
  const summary = projectionSummary(selected);
  const quality = qualityState(selected);
  const qualityLabel =
    quality.className === "verified"
      ? "Verified current stats"
      : quality.className === "flagged"
        ? "Flagged for review"
        : "Not yet verified";
  els.playerDetail.innerHTML = `
    <div class="detail-head">
      <p class="eyebrow">${escapeHtml(selected.team)} | ${escapeHtml(selected.conference)}</p>
      <h3>${escapeHtml(selected.name)}</h3>
      <p>${escapeHtml(selected.position)} | ${escapeHtml(selected.heightLabel)} | ${escapeHtml(selected.classYear)}</p>
    </div>

    <div class="primary-score">
      <span>${escapeHtml(state.destination)}</span>
      <strong>${formatNumber(projection.bpr, 2)}</strong>
      <p>${escapeHtml(projection.tier)}</p>
    </div>

    <div class="projection-bars">
      ${projectionBars(selected)}
    </div>

    <div class="stat-grid">
      ${statGrid(selected)}
    </div>

    <div class="detail-meta">
      <div class="detail-meta-row">
        <span>Best fit</span>
        <strong>${escapeHtml(summary.bestConference)} (${formatNumber(summary.bestBpr, 2)})</strong>
      </div>
      <div class="detail-meta-row">
        <span>Lowest fit</span>
        <strong>${escapeHtml(summary.worstConference)} (${formatNumber(summary.worstBpr, 2)})</strong>
      </div>
      <div class="detail-meta-row">
        <span>Data status</span>
        <strong>${escapeHtml(qualityLabel)}</strong>
      </div>
      <div class="detail-meta-row">
        <span>Source team power</span>
        <strong>${formatNumber(selected.sourceTeamPower, 2)}</strong>
      </div>
    </div>

    <div class="detail-links">
      ${
        selected.verifiedSourceUrl
          ? `<a href="${escapeHtml(selected.verifiedSourceUrl)}" target="_blank" rel="noreferrer">Open verified stat source</a>`
          : `<span class="quality-note">No linked verified stat source for this player yet.</span>`
      }
    </div>
  `;
}

function renderHeadlineMetrics(players) {
  const verified = players.filter((player) => player.verifiedCurrentStats).length;
  const flagged = players.filter((player) => player.eventStatsFlagged).length;
  const leader = players[0];
  els.visiblePlayers.textContent = formatInteger(players.length);
  els.verifiedPlayers.textContent = formatInteger(verified);
  els.flaggedPlayers.textContent = formatInteger(flagged);
  els.topProjection.textContent = leader ? formatNumber(currentProjection(leader).bpr, 2) : "-";
  els.topProjectionLabel.textContent = leader
    ? `${leader.name} | ${leader.team}`
    : "No players match the current filters";
}

function syncFilterControls() {
  els.searchInput.value = state.filters.search;
  els.destinationFilter.value = state.destination;
  els.classFilter.value = state.filters.classYear;
  els.sourceConferenceFilter.value = state.filters.sourceConference;
  els.positionFilter.value = state.filters.position;
  els.minBpr.value = String(state.filters.minBpr);
  els.minMpg.value = String(state.filters.minMpg);
  els.minPpg.value = String(state.filters.minPpg);
  els.sortSelect.value = state.filters.sort;
}

function resetFilters() {
  state.destination = DEFAULT_DESTINATION;
  state.filters = { ...DEFAULT_FILTERS };
  syncFilterControls();
}

function render() {
  renderMeta();
  renderTabs();
  els.minBprValue.textContent = formatNumber(state.filters.minBpr, 2);
  els.minMpgValue.textContent = String(state.filters.minMpg);
  els.minPpgValue.textContent = String(state.filters.minPpg);
  const players = filteredPlayers();
  if (!players.some((player) => player.id === state.selectedId)) {
    state.selectedId = players[0]?.id ?? state.players[0]?.id ?? null;
  }
  renderHeadlineMetrics(players);
  renderRows(players);
  renderDetail(players);
}

function bindEvents() {
  els.searchInput.addEventListener("input", (event) => {
    state.filters.search = event.target.value;
    render();
  });
  els.destinationFilter.addEventListener("change", (event) => {
    state.destination = event.target.value;
    render();
  });
  els.classFilter.addEventListener("change", (event) => {
    state.filters.classYear = event.target.value;
    render();
  });
  els.sourceConferenceFilter.addEventListener("change", (event) => {
    state.filters.sourceConference = event.target.value;
    render();
  });
  els.positionFilter.addEventListener("change", (event) => {
    state.filters.position = event.target.value;
    render();
  });
  els.sortSelect.addEventListener("change", (event) => {
    state.filters.sort = event.target.value;
    render();
  });
  els.resetFilters.addEventListener("click", () => {
    resetFilters();
    render();
  });
  for (const [element, key] of [
    [els.minBpr, "minBpr"],
    [els.minMpg, "minMpg"],
    [els.minPpg, "minPpg"],
  ]) {
    element.addEventListener("input", (event) => {
      state.filters[key] = Number(event.target.value);
      render();
    });
  }
  els.conferenceTabs.addEventListener("click", (event) => {
    const button = event.target.closest("[data-conference]");
    if (!button) return;
    state.destination = button.dataset.conference;
    els.destinationFilter.value = state.destination;
    render();
  });
  els.playerRows.addEventListener("click", (event) => {
    const row = event.target.closest("[data-player-id]");
    if (!row) return;
    state.selectedId = row.dataset.playerId;
    render();
  });
  els.playerDetail.addEventListener("click", (event) => {
    const button = event.target.closest("[data-conference]");
    if (!button) return;
    state.destination = button.dataset.conference;
    els.destinationFilter.value = state.destination;
    render();
  });
}

async function initialize() {
  const response = await fetch(DATA_URL);
  if (!response.ok) throw new Error(`Could not load projection data: ${response.status}`);
  state.data = await response.json();
  state.players = state.data.players;
  renderFilters();
  syncFilterControls();
  bindEvents();
  render();
}

initialize().catch((error) => {
  console.error(error);
  els.playerRows.innerHTML = `<tr><td colspan="7">Could not load projection data.</td></tr>`;
});
