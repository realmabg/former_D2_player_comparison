const CURRENT_D2_DATA_URL = "./d2_data_cleaned.csv";

const CLASS_AGE = {
  "Fr.": 18.8,
  "So.": 19.8,
  "Jr.": 20.8,
  "Sr.": 21.8,
  "Gr.": 22.8,
};

function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = "";
  let inQuotes = false;

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    const next = text[index + 1];

    if (char === '"' && inQuotes && next === '"') {
      cell += '"';
      index += 1;
      continue;
    }

    if (char === '"') {
      inQuotes = !inQuotes;
      continue;
    }

    if (char === "," && !inQuotes) {
      row.push(cell);
      cell = "";
      continue;
    }

    if ((char === "\n" || char === "\r") && !inQuotes) {
      if (char === "\r" && next === "\n") index += 1;
      row.push(cell);
      if (row.some((value) => value.length > 0)) rows.push(row);
      row = [];
      cell = "";
      continue;
    }

    cell += char;
  }

  row.push(cell);
  if (row.some((value) => value.length > 0)) rows.push(row);

  return rows;
}

function toRecords(csvText) {
  const [header, ...rows] = parseCsv(csvText);
  return rows.map((row) => {
    return Object.fromEntries(header.map((column, index) => [column, row[index] ?? ""]));
  });
}

function number(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function normalizeName(name) {
  const parts = name.split(",").map((part) => part.trim());
  if (parts.length === 2) return `${parts[1]} ${parts[0]}`;
  return name.trim();
}

function slugify(value) {
  return value
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

function mapCurrentD2Player(row, index) {
  const name = normalizeName(row["Player Name"]);
  const team = row.Team || "Unknown D2 team";
  const year = row.Year || "Current";
  const heightIn = number(row.Height, 76);
  const minutesPct = Math.min(100, (number(row.MPG) / 40) * 100);
  const fga = number(row.FGA);
  const threeAttempts = number(row["3PTA"]);

  return {
    id: `current-${slugify(`${name}-${team}-${year}`)}-${index}`,
    source: "current-d2",
    name,
    season: "Current D2",
    d2School: team,
    d1School: "Current D2 player",
    conference: row.Conference || "Unknown",
    position: row.Position || "N/A",
    heightIn,
    age: CLASS_AGE[year] ?? 21,
    minutesPct,
    usagePct: number(row.usg) * 100,
    ptsPer40: number(row.pts_per_40),
    astPer40: number(row.ast_per_40),
    tovPer40: number(row.tov_per_40),
    rebPer40: number(row.reb_per_40),
    stlPer40: number(row.stl_per_40),
    blkPer40: number(row.blk_per_40),
    threePaRate: fga > 0 ? threeAttempts / fga : number(row.three_share),
    threePct: number(row["3PT%"]),
    ftRate: number(row.FTR),
    ftPct: number(row["FT%"]),
    tsPct: number(row.TS_pct),
    confStrength: 0.5,
    d1Bpm: 0,
    d1MinutesPct: 0,
    outcomeTier: `${row.Conference || "D2"} ${year}`,
  };
}

export async function loadCurrentD2Players() {
  const response = await fetch(CURRENT_D2_DATA_URL);
  if (!response.ok) {
    throw new Error(`Could not load current D2 CSV: ${response.status}`);
  }

  const text = await response.text();
  return toRecords(text)
    .map(mapCurrentD2Player)
    .filter((player) => player.name && player.ptsPer40 > 0 && player.minutesPct > 0)
    .sort((a, b) => a.name.localeCompare(b.name));
}
