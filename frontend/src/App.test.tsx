import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { DataTable } from "./components/DataTable";
import { SearchSelect } from "./components/SearchSelect";

describe("Frontend components", () => {
  afterEach(() => {
    window.localStorage.clear();
  });

  it("SearchSelect abre opciones y filtra mientras escribes", async () => {
    const user = userEvent.setup();
    const handleChange = vi.fn();

    render(
      <SearchSelect
        label="Jugador"
        options={[
          { value: "p1", label: "#7 Jugador Uno | Team A" },
          { value: "p2", label: "#12 Jugador Dos | Team A" },
          { value: "p3", label: "#4 Jugador Tres | Team B" },
        ]}
        value=""
        onChange={handleChange}
        placeholder="Busca un jugador"
        suggestionLimit={5}
        showSelectionState={false}
      />
    );

    await user.click(screen.getByPlaceholderText("Busca un jugador"));
    expect(screen.getByText("#7 Jugador Uno | Team A")).toBeInTheDocument();

    await user.type(screen.getByPlaceholderText("Busca un jugador"), "Tres");
    expect(screen.getByRole("button", { name: /Jugador Tres/i })).toBeInTheDocument();
    expect(screen.queryByText(/Jugador Uno/i)).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Jugador Tres/i }));
    expect(handleChange).toHaveBeenCalledWith("p3");
  });

  it("DataTable permite quitar, anadir y seleccionar filas", async () => {
    const user = userEvent.setup();
    const handleSelect = vi.fn();

    render(
      <DataTable
        title="Mercado"
        columns={["JUGADOR", "EQUIPO", "PUNTOS", "ASISTENCIAS"]}
        rows={[
          { PLAYER_KEY: "p1", JUGADOR: "Jugador Uno", EQUIPO: "Team A", PUNTOS: 10, ASISTENCIAS: 4 },
          { PLAYER_KEY: "p2", JUGADOR: "Jugador Dos", EQUIPO: "Team B", PUNTOS: 8, ASISTENCIAS: 5 },
        ]}
        storageKey="test-table"
        lockedLeadingColumns={["JUGADOR"]}
        defaultVisibleColumns={["JUGADOR", "EQUIPO", "PUNTOS"]}
        onSelect={handleSelect}
      />
    );

    await user.click(screen.getByRole("button", { name: "Columnas" }));
    await user.click(screen.getByRole("button", { name: "Quitar EQUIPO" }));
    expect(screen.queryByText("EQUIPO")).not.toBeInTheDocument();

    await user.click(screen.getByPlaceholderText("Busca una columna para mostrar"));
    await user.click(screen.getByText("EQUIPO"));
    expect(screen.getAllByText("EQUIPO").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByText("Jugador Uno"));
    await waitFor(() => expect(handleSelect).toHaveBeenCalled());
  });
});
