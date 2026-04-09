import { afterEach, describe, expect, it } from "vitest";

import {
  addPlayerToMarketShortlist,
  consumeMarketIntent,
  queueMarketIntent,
  readMarketSelectedLeagues,
  readMarketShortlist,
  writeMarketSelectedLeagues,
  writeMarketShortlist,
} from "./market";

describe("market shared state", () => {
  afterEach(() => {
    window.localStorage.clear();
  });

  it("persiste las ligas seleccionadas por temporada", () => {
    writeMarketSelectedLeagues("2025-2026", ["Liga B", "Liga A", "Liga A"]);

    expect(readMarketSelectedLeagues("2025-2026", "Liga Z")).toEqual(["Liga B", "Liga A"]);
    expect(readMarketSelectedLeagues("2024-2025", "Liga Z")).toEqual(["Liga Z"]);
  });

  it("persiste la shortlist por temporada y conjunto de ligas", () => {
    writeMarketShortlist("2025-2026", ["Liga B", "Liga A"], ["p2", "p1"]);

    expect(readMarketShortlist("2025-2026", ["Liga A", "Liga B"])).toEqual(["p2", "p1"]);
    expect(readMarketShortlist("2025-2026", ["Liga A"])).toEqual([]);
  });

  it("mantiene el limite de 6 jugadores en shortlist", () => {
    let shortlist = ["p1", "p2", "p3", "p4", "p5", "p6"];
    writeMarketShortlist("2025-2026", ["Liga A"], shortlist);

    shortlist = addPlayerToMarketShortlist("2025-2026", ["Liga A"], "p7");
    expect(shortlist).toEqual(["p1", "p2", "p3", "p4", "p5", "p6"]);
  });

  it("consume intents solo en la temporada correcta", () => {
    queueMarketIntent({
      season: "2025-2026",
      league: "Liga A",
      playerKey: "p9",
      action: "target",
      source: "gm",
    });

    expect(consumeMarketIntent("2024-2025")).toBeNull();
    expect(consumeMarketIntent("2025-2026")).toEqual({
      season: "2025-2026",
      league: "Liga A",
      playerKey: "p9",
      action: "target",
      source: "gm",
    });
    expect(consumeMarketIntent("2025-2026")).toBeNull();
  });
});
