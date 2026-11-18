import type {
  AllTimeRankingsResponse,
  CompareResponse,
  DiagnosticsResponse,
  DriverProfileResponse,
  DriverSummary,
  EqualMachineryResponse,
  NetworkResponse,
  RaceXRayResponse,
  SeasonMeta,
  SeasonRacesResponse,
  SeasonRankingsResponse,
  SeatSwapResponse,
  SimulateRequestPayload,
  SimulateResponse,
  TeamLineageDetailResponse,
  TeamLineageSummary,
} from '../types/f1';

const API_BASE = '/api/v1';

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  getDriversList: (q = '') =>
    fetchJson<{ drivers: DriverSummary[]; total: number }>(
      `${API_BASE}/drivers?q=${encodeURIComponent(q)}`
    ),

  getSeasons: () => fetchJson<{ seasons: SeasonMeta[] }>(`${API_BASE}/seasons`),

  getCurrentRankings: () => fetchJson<SeasonRankingsResponse>(`${API_BASE}/rankings/current`),

  getSeasonRankings: (year: number) =>
    fetchJson<SeasonRankingsResponse>(`${API_BASE}/rankings/season/${year}`),

  getAllTimeRankings: (params: {
    decade?: number | null;
    min_starts?: number;
    nationality?: string;
    champions_only?: boolean;
    search?: string;
    sort_by?: string;
    limit?: number;
    offset?: number;
  }) => {
    const sp = new URLSearchParams();
    if (params.decade) sp.set('decade', String(params.decade));
    if (params.min_starts !== undefined) sp.set('min_starts', String(params.min_starts));
    if (params.nationality) sp.set('nationality', params.nationality);
    if (params.champions_only) sp.set('champions_only', 'true');
    if (params.search) sp.set('search', params.search);
    if (params.sort_by) sp.set('sort_by', params.sort_by);
    if (params.limit !== undefined) sp.set('limit', String(params.limit));
    if (params.offset !== undefined) sp.set('offset', String(params.offset));
    return fetchJson<AllTimeRankingsResponse>(`${API_BASE}/rankings/alltime?${sp.toString()}`);
  },

  getDriverProfile: (ref: string) =>
    fetchJson<DriverProfileResponse>(`${API_BASE}/drivers/${encodeURIComponent(ref)}`),

  compareDrivers: (driverA: string, driverB: string, mode = 'alltime', year?: number) => {
    const sp = new URLSearchParams({ driver_a: driverA, driver_b: driverB, mode });
    if (year) sp.set('year', String(year));
    return fetchJson<CompareResponse>(`${API_BASE}/compare?${sp.toString()}`);
  },

  getNetwork: (params: {
    center_driver?: string;
    decade?: number | null;
    min_shared_races?: number;
    path_from?: string;
    path_to?: string;
    max_nodes?: number;
  }) => {
    const sp = new URLSearchParams();
    if (params.center_driver) sp.set('center_driver', params.center_driver);
    if (params.decade) sp.set('decade', String(params.decade));
    if (params.min_shared_races !== undefined)
      sp.set('min_shared_races', String(params.min_shared_races));
    if (params.path_from) sp.set('path_from', params.path_from);
    if (params.path_to) sp.set('path_to', params.path_to);
    if (params.max_nodes) sp.set('max_nodes', String(params.max_nodes));
    return fetchJson<NetworkResponse>(`${API_BASE}/network?${sp.toString()}`);
  },

  simulate: (payload: SimulateRequestPayload) =>
    fetchJson<SimulateResponse>(`${API_BASE}/simulate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  getDiagnostics: () => fetchJson<DiagnosticsResponse>(`${API_BASE}/diagnostics`),

  getSeasonRaces: (year: number) =>
    fetchJson<SeasonRacesResponse>(`${API_BASE}/races/${year}`),

  getRaceXRay: (year: number, roundNumber: number) =>
    fetchJson<RaceXRayResponse>(`${API_BASE}/races/${year}/${roundNumber}`),

  getTeamLineages: () =>
    fetchJson<{ lineages: TeamLineageSummary[] }>(`${API_BASE}/teams`),

  getTeamLineageDetail: (slug: string) =>
    fetchJson<TeamLineageDetailResponse>(`${API_BASE}/teams/${encodeURIComponent(slug)}`),

  getEqualMachinery: (year: number, excludeMechanicalDnfs = true) =>
    fetchJson<EqualMachineryResponse>(
      `${API_BASE}/counterfactual/season/${year}?exclude_mechanical_dnfs=${excludeMechanicalDnfs}`
    ),

  simulateSeatSwap: (payload: {
    driver_ref: string;
    target_team_id: number;
    year: number;
    replace_driver_ref?: string;
    n_sims?: number;
  }) =>
    fetchJson<SeatSwapResponse>(`${API_BASE}/counterfactual/seat-swap`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  getPortrait: (driverRef: string) =>
    fetchJson<{ reference: string; thumbnail_url: string | null }>(
      `${API_BASE}/portraits/${encodeURIComponent(driverRef)}`
    ),

  getPortraitsBatch: (refs: string[]) =>
    fetchJson<{ portraits: Record<string, string | null> }>(
      `${API_BASE}/portraits?refs=${encodeURIComponent(refs.join(','))}`
    ),

  triggerSync: () =>
    fetchJson<{
      status: string;
      year: number;
      incremental: Record<string, unknown>;
      openf1: Record<string, unknown>;
      coverage: DiagnosticsResponse['coverage_stats'];
    }>(`${API_BASE}/admin/sync`, { method: 'POST' }),
};
