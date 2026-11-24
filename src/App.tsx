import { useEffect, useMemo, useState } from "react";
import { planJourney } from "./api";
import type { JourneyAlternative, JourneyPlanResponse, JourneyPreference } from "./types";
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
  routeSource,
}: {
  journey: JourneyAlternative;
  index: number;
  routeSource?: string;
}) {
  const [open, setOpen] = useState(index === 0);
  const source = journey.data_source || routeSource || "not provided";
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
          <p className="data-source"><strong>{source}</strong> data · occupancy and arrival estimates are not guaranteed.</p>
          {journey.stops.length > 0 && <p className="route-stops">{journey.stops.join(" → ")}</p>}
          {journey.trade_off && <p className="data-source">{journey.trade_off}</p>}
          {journey.segments?.map((segment, segmentIndex) => (
            <p className="route-stops" key={`${segment.route_id || segment.mode}-${segmentIndex}`}>
              {segment.mode === "walk" ? "Walk" : `${segment.route_id || "Route unavailable"} ${segment.trip_id || ""}`}: {segment.boarding_stop_id} → {segment.destination_stop_id}
              {" · "}{segment.data_status === "available"
                ? `${segment.expected_occupancy ?? "Occupancy unavailable"} occupancy · ${segment.crowdedness_tier || "tier unavailable"}`
                : `Crowd data ${segment.data_status}`}
            </p>
          ))}
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
  const [view, setView] = useState<"commuter" | "operations">("commuter");

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

  return (
    <main>
      <header className="topbar">
        <div><span className="brand-mark" aria-hidden="true">C</span><strong>CrowdSense</strong></div>
        <button type="button" className="avatar" aria-label="Open operations command center" onClick={() => setView("operations")}>OP</button>
      </header>

      <section className="search-panel" aria-labelledby="plan-heading">
        <div className="heading-row">
          <div><p className="eyebrow">Plan a journey</p><h1 id="plan-heading">Where to?</h1></div>
          <button type="button" className="location-button" onClick={useCurrentLocation}>⌖ Use location</button>
        </div>
        {locationStatus && <p className="location-status" role="status">{locationStatus}</p>}
        <form onSubmit={plan}>
          <label>From<input value={origin} onChange={(event) => setOrigin(event.target.value)} placeholder="Origin stop or address" /></label>
          <label>To<input value={destination} onChange={(event) => setDestination(event.target.value)} placeholder="Destination stop or address" /></label>
          <label>Departure time<input type="datetime-local" value={departureTime} onChange={(event) => setDepartureTime(event.target.value)} /></label>
          <fieldset>
            <legend>Journey preference</legend>
            <div className="preference-tabs">
              {(["fastest", "balanced", "comfort"] as JourneyPreference[]).map((choice) => (
                <button key={choice} type="button" className={preference === choice ? "active" : ""} aria-pressed={preference === choice} onClick={() => setPreferenceChoice(choice)}>{choice}</button>
              ))}
            </div>
          </fieldset>
          {preference === "balanced" && (
            <label className="comfort-slider">Comfort weight <input type="range" min="0" max="1" step="0.1" value={comfortWeight} onChange={(event) => setComfortWeight(Number(event.target.value))} /><span>{Math.round(alpha * 100)}%</span></label>
          )}
          {error && <p className="error" role="alert">{error}</p>}
          <button className="plan-button" type="submit" disabled={loading}>{loading ? "Finding routes…" : "Plan journey"}</button>
        </form>
      </section>

      {result && (
        <section className="results" aria-labelledby="results-heading">
          <div className="results-heading">
            <div><p className="eyebrow">Results</p><h2 id="results-heading">{result.origin} → {result.destination}</h2></div>
            <button type="button" onClick={saveCurrent}>♡ Save</button>
          </div>
          <p className="data-source"><strong>{result.data_source || "unknown"}</strong> · Crowd and arrival estimates are not guaranteed.</p>
          {result.alternatives.length === 0 ? (
            <p className="error" role="status">{result.detail || "No journey was found."}</p>
          ) : (
            <>
              {result.alternatives.map((journey, index) => <JourneyCard key={`${journey.type}-${index}`} journey={journey} index={index} routeSource={result.data_source} />)}
              <MapView journey={result.alternatives[0]} />
            </>
          )}
        </section>
      )}

      {recent.length > 0 && (
        <section className="saved-section"><h2>Recent journeys</h2>{recent.map((item, index) => (
          <button key={index} type="button" onClick={() => { setOrigin(item.origin); setDestination(item.destination); }}>{item.origin} → {item.destination}</button>
        ))}</section>
      )}
      {saved.length > 0 && (
        <section className="saved-section"><h2>Saved journeys</h2>{saved.map((item, index) => (
          <button key={index} type="button" onClick={() => { setOrigin(item.origin); setDestination(item.destination); }}>{item.origin} → {item.destination}</button>
        ))}</section>
      )}
    </main>
  );
}
