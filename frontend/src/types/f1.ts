export interface DriverSummary {
  driver_id: number;
  reference: string;
  abbreviation: string | null;
  name: string;
  nationality: string | null;
  country_code: string | null;
  overall: number;
  overall_raw: number;
  career_starts: number;
  career_wins: number;
  championships: number;
  first_year: number;
  last_year: number;
  primary_team_name: string;
  primary_team_color: string;
}

export interface SeasonMeta {
  year: number;
  driver_count: number;
  top_driver_name: string | null;
  top_driver_ref: string | null;
  top_driver_overall: number | null;
  top_team_name: string | null;
  top_team_color: string | null;
}

export interface SeasonDriverRating {
  rank: number;
  year: number;
  mode: string;
  driver_id: number;
  reference: string;
  abbreviation: string | null;
  forename: string;
  surname: string;
  name: string;
  nationality: string | null;
  country_code: string | null;
  permanent_car_number: number | null;
  team_id: number;
  team_name: string;
  team_color: string;
  races_count: number;
  clean_races_count: number;
  overall: number;
  overall_raw: number;
  z_final: number;
  pace_ovr: number;
  quali_ovr: number;
  consistency_ovr: number;
  racecraft_ovr: number;
  experience_ovr: number;
  z_pace: number;
  z_quali: number;
  z_consistency: number;
  z_racecraft: number;
  z_experience: number;
  car_rating: number;
  car_delta: number;
  shrinkage_weight: number;
  delta_vs_prev: number | null;
  data_tier: string;
}

export interface CarSeasonRating {
  year: number;
  team_id: number;
  team_name: string;
  team_color: string;
  car_rating: number;
  pace_car_pct: number;
  quali_car_pct: number;
}

export interface SeasonRankingsResponse {
  year: number;
  mode: string;
  rounds_analyzed: number;
  drivers: SeasonDriverRating[];
  cars: CarSeasonRating[];
}

export interface AllTimeDriverRating {
  rank?: number;
  alltime_rank?: number;
  driver_id: number;
  reference: string;
  abbreviation: string | null;
  forename: string;
  surname: string;
  name: string;
  nationality: string | null;
  country_code: string | null;
  date_of_birth?: string | null;
  permanent_car_number?: number | null;
  career_starts: number;
  career_wins: number;
  career_podiums: number;
  championships: number;
  first_year: number;
  last_year: number;
  peak_years: string;
  primary_team_name: string;
  primary_team_color: string;
  overall: number;
  overall_raw: number;
  peak_overall: number;
  longevity_overall: number;
  pace_ovr: number;
  quali_ovr: number;
  consistency_ovr: number;
  racecraft_ovr: number;
  experience_ovr: number;
  z_pace: number;
  z_quali: number;
  z_consistency: number;
  z_racecraft: number;
  z_experience: number;
  mechanical_dnfs_excluded: number;
  driver_error_dnfs: number;
  fia_penalties_count: number;
  clean_air_laps_total: number;
  data_tier: string;
}

export interface AllTimeRankingsResponse {
  total: number;
  limit: number;
  offset: number;
  drivers: AllTimeDriverRating[];
  nationalities: string[];
}

export interface TeammateRecord {
  teammate_id: number;
  teammate_ref: string;
  teammate_name: string;
  teammate_overall: number;
  shared_races: number;
  shared_quali: number;
  seasons: number[];
  teams: string[];
  quali_delta_pct: number | null;
  pace_delta_pct: number | null;
  quali_wins: number;
  quali_losses: number;
  race_wins: number;
  race_losses: number;
}

export interface RaceMetricRow {
  round_id: number;
  year: number;
  round_number: number;
  round_name: string;
  round_date: string | null;
  team_name: string;
  team_color: string;
  grid: number | null;
  finish_pos: number | null;
  status_category: string;
  fia_driving_penalties: number;
  quali_session_used: string | null;
  quali_teammate_delta_pct: number | null;
  clean_air_laps: number;
  clean_laps_total: number;
  pace_teammate_delta_pct: number | null;
  lap1_net_gain: number | null;
  on_track_overtakes: number;
  on_track_overtaken: number;
  data_tier: string;
}

export interface DriverProfileResponse {
  driver: AllTimeDriverRating;
  current_rating: SeasonDriverRating | null;
  seasons: SeasonDriverRating[];
  teammates: TeammateRecord[];
  hygiene_summary: {
    clean_finishes: number;
    mechanical_dnfs_excluded: number;
    driver_error_dnfs: number;
    dns_excluded: number;
    fia_penalties_count: number;
    clean_air_laps_total: number;
  };
  recent_races: RaceMetricRow[];
}

export interface CalibrationHop {
  from: { driver_id: number; reference: string; name: string; abbreviation: string | null };
  to: { driver_id: number; reference: string; name: string; abbreviation: string | null };
  shared_races: number;
  shared_quali: number;
  seasons: number[];
  teams: string[];
  quali_delta_pct: number | null;
  pace_delta_pct: number | null;
  quali_wins_from: number;
  quali_wins_to: number;
  race_wins_from: number;
  race_wins_to: number;
}

export interface CompareDriverSide extends AllTimeDriverRating {
  active_rating: {
    overall: number;
    overall_raw: number;
    pace_ovr: number;
    quali_ovr: number;
    consistency_ovr: number;
    racecraft_ovr: number;
    experience_ovr: number;
    team_name: string;
    team_color: string;
    races_count?: number;
    car_rating?: number;
  } | null;
}

export interface CompareResponse {
  mode: string;
  driver_a: CompareDriverSide;
  driver_b: CompareDriverSide;
  direct_teammates: {
    shared_races: number;
    shared_quali: number;
    seasons: number[];
    teams: string[];
    quali_delta_a_vs_b_pct: number | null;
    pace_delta_a_vs_b_pct: number | null;
    quali_wins_a: number;
    quali_wins_b: number;
    race_wins_a: number;
    race_wins_b: number;
  } | null;
  calibration_path: CalibrationHop[];
}

export interface NetworkNode {
  driver_id: number;
  reference: string;
  abbreviation: string | null;
  name: string;
  overall: number;
  overall_raw: number;
  career_starts: number;
  career_wins: number;
  championships: number;
  first_year: number;
  last_year: number;
  team_name: string;
  team_color: string;
}

export interface NetworkEdge {
  source: number;
  target: number;
  shared_races: number;
  shared_quali: number;
  seasons: number[];
  teams: string[];
  median_quali_delta_pct: number | null;
  median_pace_delta_pct: number | null;
  in_shortest_path: boolean;
}

export interface NetworkResponse {
  nodes: NetworkNode[];
  edges: NetworkEdge[];
  shortest_path: CalibrationHop[];
}

export interface SimulateRequestPayload {
  scope: 'current' | 'season' | 'alltime';
  year?: number | null;
  weights: {
    pace: number;
    qualifying: number;
    consistency: number;
    racecraft: number;
    experience: number;
  };
  shrinkage_m: number;
  half_life_races: number;
  base_ovr: number;
  scale_factor: number;
  min_starts: number;
  limit: number;
}

export interface SimulateResultRow {
  rank: number;
  baseline_rank: number;
  delta_rank: number;
  driver_id: number;
  reference: string;
  abbreviation: string | null;
  name: string;
  nationality: string | null;
  country_code: string | null;
  team_name: string;
  team_color: string;
  races_count: number;
  car_rating?: number;
  overall: number;
  overall_raw: number;
  baseline_overall: number;
  delta_overall: number;
  pace_ovr: number;
  quali_ovr: number;
  consistency_ovr: number;
  racecraft_ovr: number;
  experience_ovr: number;
}

export interface SimulateResponse {
  scope: string;
  year?: number;
  elapsed_ms: number;
  results: SimulateResultRow[];
}

export interface DiagnosticsResponse {
  variance_decomposition: {
    race_pace: {
      car_share_pct: number;
      driver_share_pct: number;
      total_explained_r2: number;
      car_std_pct?: number;
      driver_std_pct?: number;
      n_session_obs: number;
      n_pair_obs: number;
    };
    qualifying: {
      car_share_pct: number;
      driver_share_pct: number;
      total_explained_r2: number;
      car_std_pct?: number;
      driver_std_pct?: number;
      n_session_obs: number;
      n_pair_obs: number;
    };
  };
  age_curve: Array<{ age: number; pace_delta_pct: number; quali_delta_pct: number }>;
  lap1_grid_curve: Array<{ grid: number; expected_gain: number }>;
  coverage_stats: {
    total_drivers_rated: number;
    total_seasons: number;
    total_rounds_analyzed: number;
    total_race_entries: number;
    total_clean_air_laps: number;
    total_mechanical_dnfs_excluded: number;
    total_driver_errors_penalized: number;
    total_network_edges: number;
    latest_season: number;
    by_decade: Array<{
      decade: string;
      TELEMETRY_COMPOUND: number;
      LAP_BY_LAP: number;
      HISTORICAL_RESULT: number;
    }>;
  };
  last_updated: string;
}
