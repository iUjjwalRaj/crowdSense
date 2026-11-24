import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import MapView from "./MapView";
import { isValidCoordinate } from "../map";
import { developmentStops } from "../mapFixtures";

vi.mock("react-leaflet", () => ({
  MapContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  TileLayer: () => null,
  Polyline: () => <div data-testid="polyline" />,
  CircleMarker: ({ center, eventHandlers, children }: {
    center: [number, number];
    eventHandlers?: { click?: () => void };
    children?: React.ReactNode;
  }) => <button type="button" onClick={eventHandlers?.click}>{children}</button>,
  Tooltip: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}));

describe("interactive map", () => {
  it("only accepts valid map coordinates", () => {
    expect(isValidCoordinate(51.5074, -0.1278)).toBe(true);
    expect(isValidCoordinate(91, 0)).toBe(false);
    expect(isValidCoordinate(0, 181)).toBe(false);
  });

  it("shows selected stop occupancy and fixture disclosure", () => {
    render(<MapView journey={{ type: "balanced", stops: ["Central Square", "University Gate"], estimated_minutes: 25 }} />);
    expect(screen.getByRole("heading", { name: "Central Square" })).toBeInTheDocument();
    expect(screen.getByText(/predicted occupancy/i)).toBeInTheDocument();
    expect(screen.getByText(/Development fixture/i)).toBeInTheDocument();
  });

  it("filters crowdedness and toggles walking routes", () => {
    render(<MapView />);
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "full" } });
    expect(screen.getByText("Riverside")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("checkbox", { name: "Walking" }));
    expect(screen.getByRole("checkbox", { name: "Walking" })).not.toBeChecked();
  });

  it("development fixtures contain no invalid stop geography", () => {
    expect(developmentStops.every((stop) => isValidCoordinate(stop.lat, stop.lng))).toBe(true);
  });
});
