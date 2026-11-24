import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import OperationsCenter from "./OperationsCenter";
import { getOperationsSnapshot } from "../api";

vi.mock("../api", () => ({
  getOperationsSnapshot: vi.fn().mockResolvedValue({
    source: "live",
    timestamp: "2026-11-24T03:00:00Z",
    active_routes: 12,
    active_vehicles: 38,
    on_time_percentage: 86,
    corridors: [{ id: "D2", name: "Central - Riverside", crowd: "full", occupancy: 96 }],
  }),
  getRecommendations: vi.fn().mockResolvedValue([]),
  reviewRecommendation: vi.fn().mockResolvedValue({}),
}));

vi.mock("./MapView", () => ({
  default: () => <div aria-label="Network map fixture">Network map</div>,
}));

describe("Transit Operations Command Center", () => {
  beforeEach(() => {
    localStorage.clear();
    vi.mocked(getOperationsSnapshot).mockResolvedValue({
      source: "live",
      timestamp: "2026-11-24T03:00:00Z",
      active_routes: 12,
      active_vehicles: 38,
      on_time_percentage: 86,
      corridors: [{ id: "D2", name: "Central - Riverside", crowd: "full", occupancy: 96 }],
    });
  });

  it("shows API metrics and does not label live API data as synthetic", async () => {
    render(<OperationsCenter />);
    await waitFor(() => expect(screen.getByText("38")).toBeInTheDocument());
    expect(screen.getByText("API live")).toBeInTheDocument();
  });

  it("requires authorization and confirmation before creating an audit entry", async () => {
    vi.mocked(getOperationsSnapshot).mockRejectedValueOnce(new Error("Unavailable"));
    render(<OperationsCenter />);
    await waitFor(() => expect(screen.getByText("Draft advisory")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Draft advisory" }));
    expect(screen.getByText(/does not publish or change operations/i)).toBeInTheDocument();
    const confirm = screen.getByRole("button", { name: "Confirm & audit" });
    expect(confirm).toBeDisabled();
    fireEvent.change(screen.getByPlaceholderText("Operator name or role"), { target: { value: "Duty Controller" } });
    fireEvent.click(screen.getByRole("checkbox", { name: /confirm this advisory draft action/i }));
    expect(confirm).toBeEnabled();
    fireEvent.click(confirm);
    expect(screen.getByText(/Duty Controller/)).toBeInTheDocument();
  });

  it("shows unavailable historical data instead of invented values", async () => {
    vi.mocked(getOperationsSnapshot).mockRejectedValueOnce(new Error("Unavailable"));
    render(<OperationsCenter />);
    await waitFor(() => expect(screen.getByText(/Estimated \/ fixture/i)).toBeInTheDocument());
    expect(screen.getByText(/Unavailable/i)).toBeInTheDocument();
  });
});
