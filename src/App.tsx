import { useEffect, useMemo, useState } from "react";
import { planJourney, searchStations } from "./api";
import type { JourneyAlternative, JourneyPlanResponse, JourneyPreference, StationSearchResult } from "./types";
import MapView from "./components/MapView";
import OperationsCenter from "./components/OperationsCenter";

type SavedJourney = { origin: string; destination: string };

const RECENT_KEY = "crowdsense.recent";
const SAVED_KEY = "crowdsense.saved";
const PREF_KEY = "crowdsense.preference";

function readList(key: string): SavedJourney[] {
  try {
    return JSON.parse(localStorage.getItem(key) || "[]") as SavedJourney[];
  } catch {
    return [];
  }
}

function JourneyCard({
  journey,
  index,
}: {
  journey: JourneyAlternative;
  index: number;
}) {
  const [open, setOpen] = useState(index === 0);

  // Calculate CO2 savings vs passenger car (avg 140g CO2/km; approx 0.08kg/min transit travel)
  const co2SavedKg = Math.max(0.4, Number(((journey.estimated_minutes * 0.065)).toFixed(1)));

  return (
    <article className="journey-card">
      <button
        className="journey-summary"
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        <span className="route-mark" aria-hidden="true">{journey.type === "comfort" ? "C" : journey.type === "fastest" ? "F" : "B"}</span>
        <span className="journey-main">
          <span className="journey-title">{journey.type} route</span>
          <span className="journey-meta">{journey.estimated_minutes} min · {journey.transfers ?? "—"} transfers · {journey.walking_minutes ?? "—"} min walk</span>
        </span>
        <span className="fare">{journey.fare != null ? `₹${journey.fare}` : "Fare unavailable"}</span>
      </button>
      {open && (
        <div className="journey-details">
          <dl>
            <div><dt>Crowd cost</dt><dd>{journey.crowd_cost != null ? journey.crowd_cost : "Not available"}</dd></div>
            <div><dt>Comfort score</dt><dd>{journey.comfort_score != null ? `${journey.comfort_score}/100` : "Not available"}</dd></div>
            <div><dt>Prediction</dt><dd>{journey.uncertainty ? `${journey.uncertainty} uncertainty` : "Not available"}</dd></div>
          </dl>

          <span className="co2-badge">🌱 ~{co2SavedKg} kg CO₂ saved</span>

          {/* Turn-by-turn segment breakdown */}
          {journey.segments && journey.segments.length > 0 && (
            <div className="timeline-container" aria-label="Trip itinerary segments">
              {journey.segments.map((segment, segmentIndex) => {
                const isWalk = segment.mode === "walk";
                const bName = segment.boarding_stop_name || segment.boarding_stop_id;
                const dName = segment.destination_stop_name || segment.destination_stop_id;
                return (
                  <div key={`${segment.route_id || segment.mode}-${segmentIndex}`} className="timeline-item">
                    <span className={`timeline-dot ${isWalk ? "walk" : ""}`} />
                    <div className="timeline-content">
                      <div className="timeline-title">
                        <span>{isWalk ? "🚶 Walk" : `🚇 ${segment.route_id || "Transit"}`}</span>
                        <span className="timeline-badge">
                          {isWalk ? `${segment.walking_minutes} min` : `${segment.travel_minutes} min`}
                        </span>
                      </div>
                      <div className="timeline-sub">
                        <strong>{bName}</strong> → <strong>{dName}</strong>
                        {segment.headsign && <span> · {segment.headsign}</span>}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          <div className="itinerary-actions">
            <button
              type="button"
              className="itinerary-action-btn"
              onClick={() => window.print()}
            >
              🖨️ Export Itinerary
            </button>
          </div>
        </div>
      )}
    </article>
  );
}

export default function App() {
  const [origin, setOrigin] = useState("");
  const [destination, setDestination] = useState("");
  const [departureTime, setDepartureTime] = useState("");
  const [preference, setPreference] = useState<JourneyPreference>(
    (localStorage.getItem(PREF_KEY) as JourneyPreference) || "balanced",
  );
  const [comfortWeight, setComfortWeight] = useState(preference === "comfort" ? 0.8 : preference === "fastest" ? 0.2 : 0.5);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<JourneyPlanResponse | null>(null);
  const [recent, setRecent] = useState<SavedJourney[]>(() => readList(RECENT_KEY));
  const [saved, setSaved] = useState<SavedJourney[]>(() => readList(SAVED_KEY));
  const [locationStatus, setLocationStatus] = useState("");
  const [view, setView] = useState<"commuter" | "operations" | "network">("commuter");

  // Autocomplete suggestions
  const [originSuggestions, setOriginSuggestions] = useState<StationSearchResult[]>([]);
  const [destSuggestions, setDestSuggestions] = useState<StationSearchResult[]>([]);
  const [showOriginSug, setShowOriginSug] = useState(false);
  const [showDestSug, setShowDestSug] = useState(false);

  useEffect(() => {
    localStorage.setItem(PREF_KEY, preference);
  }, [preference]);

  const alpha = useMemo(() => {
    if (preference === "comfort") return 0.8;
    if (preference === "fastest") return 0.2;
    return comfortWeight;
  }, [comfortWeight, preference]);

  function setPreferenceChoice(value: JourneyPreference) {
    setPreference(value);
    setComfortWeight(value === "comfort" ? 0.8 : value === "fastest" ? 0.2 : 0.5);
  }

  function handleOriginChange(val: string) {
    setOrigin(val);
    if (val.trim().length >= 2) {
      searchStations(val).then((stops) => {
        setOriginSuggestions(stops);
        setShowOriginSug(true);
      });
    } else {
      setShowOriginSug(false);
    }
  }

  function handleDestChange(val: string) {
    setDestination(val);
    if (val.trim().length >= 2) {
      searchStations(val).then((stops) => {
        setDestSuggestions(stops);
        setShowDestSug(true);
      });
    } else {
      setShowDestSug(false);
    }
  }

  function swapStations() {
    const temp = origin;
    setOrigin(destination);
    setDestination(temp);
  }

  function setPresetTime(type: "now" | "peak_morning" | "peak_evening") {
    const now = new Date();
    if (type === "now") {
      // ISO string trimmed to minutes
      const tzOffset = now.getTimezoneOffset() * 60000;
      const localISOTime = new Date(now.getTime() - tzOffset).toISOString().slice(0, 16);
      setDepartureTime(localISOTime);
    } else if (type === "peak_morning") {
      now.setHours(8, 30, 0, 0);
      const tzOffset = now.getTimezoneOffset() * 60000;
      setDepartureTime(new Date(now.getTime() - tzOffset).toISOString().slice(0, 16));
    } else if (type === "peak_evening") {
      now.setHours(18, 0, 0, 0);
      const tzOffset = now.getTimezoneOffset() * 60000;
      setDepartureTime(new Date(now.getTime() - tzOffset).toISOString().slice(0, 16));
    }
  }

  function useCurrentLocation() {
    setLocationStatus("Locating…");
    if (!navigator.geolocation) {
      setLocationStatus("Location unavailable");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        setOrigin(`${position.coords.latitude.toFixed(5)}, ${position.coords.longitude.toFixed(5)}`);
        setLocationStatus("Current coordinates used");
      },
      () => setLocationStatus("Could not access location"),
      { enableHighAccuracy: true, timeout: 8000 },
    );
  }

  async function plan(event: React.FormEvent) {
    event.preventDefault();
    setShowOriginSug(false);
    setShowDestSug(false);
    if (!origin.trim() || !destination.trim()) {
      setError("Enter both an origin and destination.");
      return;
    }
    setLoading(true);
    setError("");
    const controller = new AbortController();
    try {
      const data = await planJourney(origin.trim(), destination.trim(), alpha, departureTime, controller.signal, preference);
      setResult(data);
      const pair = { origin: origin.trim(), destination: destination.trim() };
      const next = [pair, ...recent.filter((item) => item.origin !== pair.origin || item.destination !== pair.destination)].slice(0, 6);
      setRecent(next);
      localStorage.setItem(RECENT_KEY, JSON.stringify(next));
    } catch (caught) {
      if (caught instanceof TypeError) {
        setError("Journey planning failed (backend unavailable)");
      } else {
        setError(caught instanceof Error ? caught.message : "Unable to plan this journey.");
      }
    } finally {
      setLoading(false);
    }
  }

  function saveCurrent() {
    if (!origin.trim() || !destination.trim()) return;
    const pair = { origin: origin.trim(), destination: destination.trim() };
    const next = [pair, ...saved.filter((item) => item.origin !== pair.origin || item.destination !== pair.destination)].slice(0, 12);
    setSaved(next);
    localStorage.setItem(SAVED_KEY, JSON.stringify(next));
  }

  if (view === "operations") {
    return (
      <div>
        <button className="view-switch" type="button" onClick={() => setView("commuter")}>Commuter view</button>
        <OperationsCenter />
      </div>
    );
  }

  const popularHubs = [
    { label: "Rajiv Chowk", val: "Rajiv Chowk" },
    { label: "Noida Sec 62", val: "Noida Sector 62" },
    { label: "Anand Vihar", val: "Anand Vihar" },
    { label: "Kashmere Gate", val: "Kashmere Gate" },
    { label: "New Delhi", val: "New Delhi" },
    { label: "Hapur", val: "Hapur" },
    { label: "Patna", val: "Patna" },
  ];

  return (
    <div>
      <header className="topbar">
        <div className="brand-group">
          <span className="brand-mark" aria-hidden="true">C</span>
          <div className="brand-text">
            <strong>CrowdSense</strong>
          </div>
        </div>

        <div className="topbar-actions">
          <button
            type="button"
            className={`nav-tab-btn ${view === "commuter" ? "active" : ""}`}
            onClick={() => setView("commuter")}
          >
            Planner
          </button>
          <button
            type="button"
            className={`nav-tab-btn ${view === "network" ? "active" : ""}`}
            onClick={() => setView("network")}
          >
            Map
          </button>
          <button
            type="button"
            className="avatar"
            aria-label="Open operations command center"
            onClick={() => setView("operations")}
          >
            OP
          </button>
        </div>
      </header>

      <main>
        {view === "network" ? (
          <section className="search-panel">
            <div className="heading-row">
              <div>
                <h2>Network Map</h2>
              </div>
              <button type="button" className="location-button" onClick={() => setView("commuter")}>
                Back
              </button>
            </div>
            <MapView />
          </section>
        ) : (
          <>
            <section className="search-panel" aria-labelledby="plan-heading">
              <div className="heading-row">
                <div>
                  <p className="eyebrow">Plan a journey</p>
                  <h1 id="plan-heading">Where to?</h1>
                </div>
                <button type="button" className="location-button" onClick={useCurrentLocation}>
                  ⌖ Use location
                </button>
              </div>
              {locationStatus && <p className="location-status" role="status">{locationStatus}</p>}

              {/* Quick Hub Presets */}
              <div className="hub-section">
                <span className="eyebrow">Popular Transit Hubs:</span>
                <div className="hub-pills">
                  {popularHubs.map((hub) => (
                    <button
                      key={hub.val}
                      type="button"
                      className="hub-pill"
                      onClick={() => {
                        if (!origin) {
                          setOrigin(hub.val);
                        } else if (!destination && destination !== hub.val) {
                          setDestination(hub.val);
                        } else {
                          setDestination(hub.val);
                        }
                      }}
                    >
                      + {hub.label}
                    </button>
                  ))}
                </div>
              </div>

              <form onSubmit={plan}>
                <div className="input-with-swap">
                  <div className="input-field-wrap">
                    <label>
                      From
                      <input
                        value={origin}
                        onChange={(event) => handleOriginChange(event.target.value)}
                        onFocus={() => { if (originSuggestions.length > 0) setShowOriginSug(true); }}
                        placeholder="Origin stop or address"
                        autoComplete="off"
                      />
                    </label>
                    {showOriginSug && originSuggestions.length > 0 && (
                      <div className="suggestions-box">
                        {originSuggestions.map((s) => (
                          <button
                            key={s.id}
                            type="button"
                            className="suggestion-row"
                            onClick={() => {
                              setOrigin(s.name);
                              setShowOriginSug(false);
                            }}
                          >
                            <span>{s.name}</span>
                            <span style={{ fontSize: "0.72rem", color: "#70a6ca" }}>{s.code || s.id}</span>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="swap-btn-container">
                    <button
                      type="button"
                      className="swap-btn"
                      onClick={swapStations}
                      title="Swap origin and destination"
                    >
                      ⇄ Swap
                    </button>
                  </div>

                  <div className="input-field-wrap">
                    <label>
                      To
                      <input
                        value={destination}
                        onChange={(event) => handleDestChange(event.target.value)}
                        onFocus={() => { if (destSuggestions.length > 0) setShowDestSug(true); }}
                        placeholder="Destination stop or address"
                        autoComplete="off"
                      />
                    </label>
                    {showDestSug && destSuggestions.length > 0 && (
                      <div className="suggestions-box">
                        {destSuggestions.map((s) => (
                          <button
                            key={s.id}
                            type="button"
                            className="suggestion-row"
                            onClick={() => {
                              setDestination(s.name);
                              setShowDestSug(false);
                            }}
                          >
                            <span>{s.name}</span>
                            <span style={{ fontSize: "0.72rem", color: "#70a6ca" }}>{s.code || s.id}</span>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                <label>
                  Departure time
                  <input
                    type="datetime-local"
                    value={departureTime}
                    onChange={(event) => setDepartureTime(event.target.value)}
                  />
                  <div className="time-chips">
                    <button type="button" className="time-chip" onClick={() => setPresetTime("now")}>Leave Now</button>
                    <button type="button" className="time-chip" onClick={() => setPresetTime("peak_morning")}>Morning Peak (08:30)</button>
                    <button type="button" className="time-chip" onClick={() => setPresetTime("peak_evening")}>Evening Peak (18:00)</button>
                  </div>
                </label>

                <fieldset>
                  <legend>Journey preference</legend>
                  <div className="preference-tabs">
                    {(["fastest", "balanced", "comfort"] as JourneyPreference[]).map((choice) => (
                      <button
                        key={choice}
                        type="button"
                        className={preference === choice ? "active" : ""}
                        aria-pressed={preference === choice}
                        onClick={() => setPreferenceChoice(choice)}
                      >
                        {choice}
                      </button>
                    ))}
                  </div>
                </fieldset>

                {preference === "balanced" && (
                  <label className="comfort-slider">
                    Comfort weight
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.1"
                      value={comfortWeight}
                      onChange={(event) => setComfortWeight(Number(event.target.value))}
                    />
                    <span>{Math.round(alpha * 100)}%</span>
                  </label>
                )}

                {error && <p className="error" role="alert">{error}</p>}
                <button className="plan-button" type="submit" disabled={loading}>
                  {loading ? "Finding routes…" : "Plan journey"}
                </button>
              </form>
            </section>

            {result && (
              <section className="results" aria-labelledby="results-heading">
                <div className="results-heading">
                  <div>
                    <p className="eyebrow">Results</p>
                    <h2 id="results-heading">{result.origin} → {result.destination}</h2>
                  </div>
                  <button type="button" onClick={saveCurrent}>♡ Save</button>
                </div>
                <p className="data-source">
                  <strong>{result.data_source || "unknown"}</strong> · Crowd and arrival estimates are not guaranteed.
                </p>
                {result.alternatives.length === 0 ? (
                  <p className="error" role="status">{result.detail || "No journey was found."}</p>
                ) : (
                  <>
                    {result.alternatives.map((journey, index) => (
                      <JourneyCard
                        key={`${journey.type}-${index}`}
                        journey={journey}
                        index={index}
                      />
                    ))}
                    <MapView journey={result.alternatives[0]} />
                  </>
                )}
              </section>
            )}

            {recent.length > 0 && (
              <section className="saved-section">
                <h2>Recent journeys</h2>
                {recent.map((item, index) => (
                  <button
                    key={index}
                    type="button"
                    onClick={() => { setOrigin(item.origin); setDestination(item.destination); }}
                  >
                    {item.origin} → {item.destination}
                  </button>
                ))}
              </section>
            )}

            {saved.length > 0 && (
              <section className="saved-section">
                <h2>Saved journeys</h2>
                {saved.map((item, index) => (
                  <button
                    key={index}
                    type="button"
                    onClick={() => { setOrigin(item.origin); setDestination(item.destination); }}
                  >
                    {item.origin} → {item.destination}
                  </button>
                ))}
              </section>
            )}
          </>
        )}
      </main>
    </div>
  );
}
