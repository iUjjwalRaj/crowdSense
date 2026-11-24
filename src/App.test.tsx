import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App";

vi.mock("react-leaflet", () => ({
  MapContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  TileLayer: () => <div data-testid="tile-layer" />,
  Polyline: () => <div data-testid="polyline" />,
  CircleMarker: ({ center, eventHandlers, children }: {
    center: [number, number];
    eventHandlers?: { click?: () => void };
    children?: React.ReactNode;
  }) => <button type="button" data-testid={`stop-${center.join("-")}`} onClick={eventHandlers?.click}>{children}</button>,
  Tooltip: ({ children }: { children: React.ReactNode }) => <span>{children}</span>,
}));

describe("CrowdSense journey planner", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.restoreAllMocks();
  });

  it("requires origin and destination", async () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "Plan journey" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Enter both");
  });

  it("renders API alternatives and clearly marks estimates", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        origin: "A",
        destination: "B",
        data_source: "predicted",
        alternatives: [{
          type: "balanced",
          stops: ["A", "B"],
          estimated_minutes: 25,
          crowd_cost: 1,
          fare: 30,
          walking_minutes: 4,
          transfers: 1,
          comfort_score: 72,
          uncertainty: "medium",
        }],
      }),
    }));
    render(<App />);
    fireEvent.change(screen.getByPlaceholderText("Origin stop or address"), { target: { value: "A" } });
    fireEvent.change(screen.getByPlaceholderText("Destination stop or address"), { target: { value: "B" } });
    fireEvent.click(screen.getByRole("button", { name: "Plan journey" }));
    expect(await screen.findByRole("heading", { name: "A → B" })).toBeInTheDocument();
    expect(screen.getByText(/Crowd and arrival estimates are not guaranteed/i)).toBeInTheDocument();
  });

  it("renders a no-route state without fabricated alternatives", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        status: "no_route",
        origin: "A",
        destination: "Z",
        detail: "No scheduled or valid walking route was found.",
        alternatives: [],
      }),
    }));
    render(<App />);
    fireEvent.change(screen.getByPlaceholderText("Origin stop or address"), { target: { value: "A" } });
    fireEvent.change(screen.getByPlaceholderText("Destination stop or address"), { target: { value: "Z" } });
    fireEvent.click(screen.getByRole("button", { name: "Plan journey" }));
    expect(await screen.findByRole("status")).toHaveTextContent("No scheduled or valid walking route");
  });

  it("saves preference locally", () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "comfort" }));
    expect(localStorage.getItem("crowdsense.preference")).toBe("comfort");
  });
});
