import { Fragment } from "react";

import type { MarketCompareMetric, MarketComparePlayer } from "../types";
import { formatNumber } from "../utils";

function formatDelta(value: number | null) {
  if (value == null || !Number.isFinite(value)) {
    return "";
  }
  if (Math.abs(value) < 0.01) {
    return "Top del shortlist";
  }
  const prefix = value > 0 ? "+" : "";
  return `vs mejor ${prefix}${formatNumber(value, 1)}`;
}

function findMetricRow(metric: MarketCompareMetric, playerKey: string) {
  return metric.rows.find((row) => row.playerKey === playerKey) ?? null;
}

export function MarketCompareBlock({
  block,
  players,
}: {
  block: { key: string; title: string; metrics: MarketCompareMetric[] };
  players: MarketComparePlayer[];
}) {
  return (
    <section className="panel panel-soft market-compare-block">
      <div className="page-header market-compare-header">
        <div>
          <span className="eyebrow">Comparador</span>
          <h3>{block.title}</h3>
        </div>
      </div>

      <div
        className="market-compare-grid"
        style={{ gridTemplateColumns: `minmax(140px, 1.1fr) repeat(${players.length}, minmax(150px, 1fr))` }}
      >
        <div className="market-compare-grid-head">Métrica</div>
        {players.map((player) => (
          <div key={`${block.key}-${player.playerKey}-head`} className="market-compare-grid-head">
            <strong>{player.name}</strong>
            <span>{player.team}</span>
          </div>
        ))}

        {block.metrics.map((metric) => (
          <Fragment key={`${block.key}-${metric.key}`}>
            <div className="market-compare-grid-label">
              <strong>{metric.label}</strong>
            </div>
            {players.map((player) => {
              const metricRow = findMetricRow(metric, player.playerKey);
              return (
                <div key={`${block.key}-${metric.key}-${player.playerKey}`} className="market-compare-grid-cell">
                  <strong>{metricRow?.formatted ?? "-"}</strong>
                  {metricRow?.percentile != null ? <span>Pctl {formatNumber(metricRow.percentile, 0)}</span> : null}
                  {metricRow?.deltaToBest != null ? <span>{formatDelta(metricRow.deltaToBest)}</span> : null}
                </div>
              );
            })}
          </Fragment>
        ))}
      </div>
    </section>
  );
}
