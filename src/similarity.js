export function buildStats(players, features) {
  return features.reduce((stats, feature) => {
    const values = players.map((player) => player[feature.key]);
    const mean = values.reduce((sum, value) => sum + value, 0) / values.length;
    const variance =
      values.reduce((sum, value) => sum + (value - mean) ** 2, 0) / values.length;
    stats[feature.key] = {
      mean,
      std: Math.sqrt(variance) || 1,
    };
    return stats;
  }, {});
}

export function zScore(player, feature, stats) {
  const metric = stats[feature.key];
  return (player[feature.key] - metric.mean) / metric.std;
}

export function weightedDistance(target, candidate, features, stats, weights) {
  const totalWeight = features.reduce((sum, feature) => sum + weights[feature.key], 0);
  const squared = features.reduce((sum, feature) => {
    const targetZ = zScore(target, feature, stats);
    const candidateZ = zScore(candidate, feature, stats);
    return sum + weights[feature.key] * (targetZ - candidateZ) ** 2;
  }, 0);

  return Math.sqrt(squared / totalWeight);
}

export function findMatches(target, players, features, weights, options = {}) {
  const stats = buildStats(players, features);
  const pool = players.filter((player) => {
    if (options.hideTarget && player.id === target.id) return false;
    return true;
  });

  return pool
    .map((candidate) => {
      const distance = weightedDistance(target, candidate, features, stats, weights);
      return {
        player: candidate,
        distance,
        similarity: Math.max(0, Math.round((1 - distance / 3.25) * 100)),
      };
    })
    .sort((a, b) => a.distance - b.distance);
}

export function profileScores(player, features, players) {
  const stats = buildStats(players, features);
  return features.map((feature) => {
    const raw = zScore(player, feature, stats);
    const oriented = feature.higherIsBetter ? raw : raw * -1;
    return {
      key: feature.key,
      label: feature.label,
      value: raw,
      oriented,
    };
  });
}
