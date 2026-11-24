import { expect, test } from "@playwright/test";

test("plans a journey from the API response", async ({ page }) => {
  await page.route("**/api/v1/journey/plan", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        origin: "Central",
        destination: "Airport",
        data_source: "predicted",
        alternatives: [{
          type: "fastest",
          stops: ["Central", "Airport"],
          estimated_minutes: 32,
          fare: 45,
          walking_minutes: 5,
          transfers: 1,
          comfort_score: 68,
          uncertainty: "medium",
        }],
      }),
    });
  });
  await page.goto("/");
  await page.getByPlaceholder("Origin stop or address").fill("Central");
  await page.getByPlaceholder("Destination stop or address").fill("Airport");
  await page.getByRole("button", { name: "Plan journey" }).click();
  await expect(page.getByRole("heading", { name: "Central → Airport" })).toBeVisible();
  await expect(page.getByText(/Crowd and arrival estimates are not guaranteed/i)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Route map" })).toBeVisible();
  await expect(page.getByText(/Development fixture/i)).toBeVisible();
});

test("shows a no-route response from the real API contract", async ({ page }) => {
  await page.route("**/api/v1/journey/plan", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "no_route",
        origin: "A",
        destination: "Z",
        detail: "No scheduled or valid walking route was found.",
        alternatives: [],
      }),
    });
  });
  await page.goto("/");
  await page.getByPlaceholder("Origin stop or address").fill("A");
  await page.getByPlaceholder("Destination stop or address").fill("Z");
  await page.getByRole("button", { name: "Plan journey" }).click();
  await expect(page.getByRole("status")).toContainText("No scheduled or valid walking route");
});

test("shows backend-unavailable behavior without a fabricated journey", async ({ page }) => {
  await page.route("**/api/v1/journey/plan", async (route) => route.abort("connectionfailed"));
  await page.goto("/");
  await page.getByPlaceholder("Origin stop or address").fill("A");
  await page.getByPlaceholder("Destination stop or address").fill("Z");
  await page.getByRole("button", { name: "Plan journey" }).click();
  await expect(page.getByRole("alert")).toContainText("backend unavailable");
  await expect(page.getByText(/A → Z/)).toHaveCount(0);
});

test("shows real missing-GTFS state when transport data is unconfigured", async ({ page }) => {
  await page.route("**/api/v1/journey/plan", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "data_unavailable",
        origin: "Patna",
        destination: "Delhi",
        alternatives: [],
        detail: "GTFS transport data is not configured.",
      }),
    });
  });
  await page.goto("/");
  await page.getByPlaceholder("Origin stop or address").fill("Patna");
  await page.getByPlaceholder("Destination stop or address").fill("Delhi");
  await page.getByRole("button", { name: "Plan journey" }).click();
  await expect(page.getByRole("status")).toContainText("GTFS transport data is not configured");
  await expect(page.getByText(/Journey planning failed \(500\)/)).toHaveCount(0);
});

test("plans a real journey for Hapur to Noida Sector 62", async ({ page }) => {
  await page.route("**/api/v1/journey/plan", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "ok",
        origin: "Hapur",
        destination: "Noida Sector 62",
        data_source: "gtfs",
        alternatives: [{
          type: "fastest",
          stops: ["HPU", "GZB", "ANVT", "74", "89", "237"],
          estimated_minutes: 179.4,
          transfers: 2,
          walking_minutes: 3.5,
          uncertainty: "high",
          segments: [
            { mode: "transit", boarding_stop_id: "HPU", destination_stop_id: "GZB", route_id: "ir_64567", travel_minutes: 44, waiting_minutes: 0, walking_minutes: 0, transfer: false },
            { mode: "walk", boarding_stop_id: "ANVT", destination_stop_id: "74", travel_minutes: 0, waiting_minutes: 0, walking_minutes: 3.5, transfer: true },
            { mode: "transit", boarding_stop_id: "74", destination_stop_id: "237", route_id: "dmrc_3123", travel_minutes: 39, waiting_minutes: 2, walking_minutes: 0, transfer: true },
          ],
        }],
      }),
    });
  });
  await page.goto("/");
  await page.getByPlaceholder("Origin stop or address").fill("Hapur");
  await page.getByPlaceholder("Destination stop or address").fill("Noida Sector 62");
  await page.getByRole("button", { name: "Plan journey" }).click();
  await expect(page.getByRole("heading", { name: "Hapur → Noida Sector 62" })).toBeVisible();
  await expect(page.getByText(/Crowd and arrival estimates are not guaranteed/i)).toBeVisible();
});

test("plans a real journey for Patna to Delhi", async ({ page }) => {
  await page.route("**/api/v1/journey/plan", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        status: "ok",
        origin: "Patna",
        destination: "Delhi",
        data_source: "gtfs",
        alternatives: [{
          type: "fastest",
          stops: ["PNBE", "ARA", "BXR", "DDU", "CNB", "NDLS"],
          estimated_minutes: 836.5,
          transfers: 0,
          walking_minutes: 0,
          uncertainty: "high",
          segments: [
            { mode: "transit", boarding_stop_id: "PNBE", destination_stop_id: "NDLS", route_id: "ir_12423", travel_minutes: 836.5, waiting_minutes: 0, walking_minutes: 0, transfer: false },
          ],
        }],
      }),
    });
  });
  await page.goto("/");
  await page.getByPlaceholder("Origin stop or address").fill("Patna");
  await page.getByPlaceholder("Destination stop or address").fill("Delhi");
  await page.getByRole("button", { name: "Plan journey" }).click();
  await expect(page.getByRole("heading", { name: "Patna → Delhi" })).toBeVisible();
  await expect(page.getByText(/Crowd and arrival estimates are not guaranteed/i)).toBeVisible();
});

test("interacts with live backend for real journey planning", async ({ page }) => {
  await page.goto("/");
  await page.getByPlaceholder("Origin stop or address").fill("Hapur");
  await page.getByPlaceholder("Destination stop or address").fill("Noida Sector 62");
  await page.getByRole("button", { name: "Plan journey" }).click();
  await expect(page.getByRole("heading", { name: "Hapur → Noida Sector 62" })).toBeVisible({ timeout: 15000 });
  await expect(page.getByText(/Crowd and arrival estimates are not guaranteed/i)).toBeVisible();
});

test("opens the operations command center with API status", async ({ page }) => {
  await page.route("**/api/v1/occ/occupancy/corridor", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        source: "live",
        active_routes: 12,
        active_vehicles: 38,
        on_time_percentage: 86,
        corridors: [{ id: "D2", name: "Central - Riverside", crowd: "full", occupancy: 96 }],
      }),
    });
  });
  await page.goto("/");
  await page.getByRole("button", { name: "Open operations command center" }).click();
  await expect(page.getByRole("heading", { name: "Command Center" })).toBeVisible();
  await expect(page.getByText("API live")).toBeVisible();
  await expect(page.getByText("38")).toBeVisible();
});
