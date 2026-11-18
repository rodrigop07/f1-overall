import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowLeft,
  Calendar,
  CloudRain,
  Compass,
  Flag,
  Flame,
  Gauge,
  Trophy,
} from 'lucide-react';
import { api } from '../api/client';
import { CountryFlag } from '../components/CountryFlag';
import { DriverAvatar } from '../components/DriverAvatar';
import { OverallBadge } from '../components/OverallBadge';
import type { RaceXRayResponse, SeasonMeta, SeasonRacesResponse } from '../types/f1';

function circuitTypeMeta(ct: string) {
  switch (ct) {
    case 'STREET':
      return { label: 'Circuito de Rua', icon: Compass, cls: 'bg-amber-500/15 text-amber-300 border-amber-400/30' };
    case 'HIGH_SPEED':
      return { label: 'Alta Velocidade', icon: Gauge, cls: 'bg-red-500/15 text-red-300 border-red-400/30' };
    default:
      return { label: 'Técnico / Misto', icon: Flag, cls: 'bg-slate-500/15 text-slate-300 border-slate-400/30' };
  }
}

function compoundColor(compound: string): { bg: string; text: string; short: string } {
  const c = compound.toUpperCase();
  if (c.includes('SOFT') || c === 'C4' || c === 'C5') return { bg: '#EF4444', text: '#FFFFFF', short: 'S' };
  if (c.includes('MED')) return { bg: '#FACC15', text: '#090B10', short: 'M' };
  if (c.includes('HARD')) return { bg: '#E2E8F0', text: '#090B10', short: 'H' };
  if (c.includes('INTER')) return { bg: '#22C55E', text: '#090B10', short: 'I' };
  if (c.includes('WET')) return { bg: '#3B82F6', text: '#FFFFFF', short: 'W' };
  return { bg: '#64748B', text: '#FFFFFF', short: c.slice(0, 1) || '?' };
}

export function RaceExplorerPage() {
  const { year: yearParam, roundNumber: roundParam } = useParams<{
    year?: string;
    roundNumber?: string;
  }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  const isDetail = Boolean(yearParam && roundParam);
  const queryYear = Number(searchParams.get('year'));
  const initialYear = yearParam
    ? Number(yearParam)
    : queryYear && !Number.isNaN(queryYear)
      ? queryYear
      : 2026;

  const [selectedYear, setSelectedYear] = useState<number>(initialYear);
  const [seasons, setSeasons] = useState<SeasonMeta[]>([]);
  const [seasonRaces, setSeasonRaces] = useState<SeasonRacesResponse | null>(null);
  const [raceDetail, setRaceDetail] = useState<RaceXRayResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (yearParam) {
      setSelectedYear(Number(yearParam));
    } else if (queryYear && !Number.isNaN(queryYear)) {
      setSelectedYear(queryYear);
    }
  }, [yearParam, queryYear]);

  useEffect(() => {
    api.getSeasons().then((res) => setSeasons(res.seasons)).catch(() => {});
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    if (isDetail && yearParam && roundParam) {
      Promise.all([
        api.getRaceXRay(Number(yearParam), Number(roundParam)),
        api.getSeasonRaces(Number(yearParam)).catch(() => null),
      ])
        .then(([detail, list]) => {
          if (!cancelled) {
            setRaceDetail(detail);
            if (list) setSeasonRaces(list);
          }
        })
        .catch((err) => {
          if (!cancelled) setError(err instanceof Error ? err.message : 'GP não encontrado');
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    } else {
      setRaceDetail(null);
      api
        .getSeasonRaces(selectedYear)
        .then((res) => {
          if (!cancelled) setSeasonRaces(res);
        })
        .catch((err) => {
          if (!cancelled) setError(err instanceof Error ? err.message : 'Temporada não encontrada');
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }

    return () => {
      cancelled = true;
    };
  }, [isDetail, yearParam, roundParam, selectedYear]);

  const maxLap = useMemo(() => {
    if (!raceDetail?.stints.length) return 60;
    return Math.max(1, ...raceDetail.stints.map((s) => s.lap_end));
  }, [raceDetail]);

  const stintsByDriver = useMemo(() => {
    if (!raceDetail?.stints.length) return [];
    const map = new Map<
      number,
      {
        driver_id: number;
        reference: string;
        name: string;
        abbreviation: string | null;
        team_color: string;
        weekend_score: number;
        stints: RaceXRayResponse['stints'];
      }
    >();
    const colorMap = new Map<number, string>();
    const scoreMap = new Map<number, number>();
    raceDetail.drivers.forEach((d) => {
      colorMap.set(d.driver_id, d.team_color);
      scoreMap.set(d.driver_id, d.weekend_score);
    });
    for (const s of raceDetail.stints) {
      let group = map.get(s.driver_id);
      if (!group) {
        group = {
          driver_id: s.driver_id,
          reference: s.reference,
          name: s.name,
          abbreviation: s.abbreviation,
          team_color: colorMap.get(s.driver_id) || '#64748B',
          weekend_score: scoreMap.get(s.driver_id) ?? 0,
          stints: [],
        };
        map.set(s.driver_id, group);
      }
      group.stints.push(s);
    }
    return Array.from(map.values()).sort((a, b) => b.weekend_score - a.weekend_score);
  }, [raceDetail]);

  const globalPaceBounds = useMemo(() => {
    if (!raceDetail?.lap_distributions.length) return { min: 70, max: 110 };
    const mins = raceDetail.lap_distributions.map((l) => l.min_sec);
    const maxs = raceDetail.lap_distributions.map((l) => l.max_sec);
    return { min: Math.min(...mins), max: Math.max(...maxs) };
  }, [raceDetail]);

  return (
    <div className="space-y-6">
      {/* Header Banner */}
      <section className="rounded-2xl border border-white/10 bg-gradient-to-br from-[#141927] via-[#0e121c] to-[#090B10] p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            {isDetail ? (
              <Link
                to={`/races?year=${selectedYear}`}
                className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-400 hover:text-white mb-2"
              >
                <ArrowLeft className="h-3.5 w-3.5" /> Voltar para o calendário de {selectedYear}
              </Link>
            ) : (
              <div className="inline-flex items-center gap-2 rounded-full border border-[#E10600]/40 bg-[#E10600]/10 px-3 py-1 text-[11px] font-bold uppercase tracking-wider text-red-300">
                <Flag className="h-3.5 w-3.5" /> Raio-X por Grande Prêmio (1950–2026)
              </div>
            )}

            <h1 className="mt-2 text-2xl font-black tracking-tight text-white sm:text-3xl">
              {isDetail && raceDetail
                ? `${raceDetail.round.year} ${raceDetail.round.name}`
                : `Calendário & Nota de Fim de Semana (${selectedYear})`}
            </h1>
            <p className="mt-1 text-sm text-slate-400">
              {isDetail && raceDetail
                ? `${raceDetail.round.circuit_name ?? ''} · ${raceDetail.round.locality ?? ''}, ${raceDetail.round.country ?? ''}`
                : 'Veja a nota isolada por fim de semana (Nota FDS), classificação de circuito, clima e o Destaque do GP.'}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            {!isDetail && (
              <select
                value={selectedYear}
                onChange={(e) => {
                  const yr = Number(e.target.value);
                  setSelectedYear(yr);
                  setSearchParams({ year: String(yr) });
                }}
                aria-label="Selecionar temporada"
                className="rounded-xl border border-white/15 bg-[#121622] px-3.5 py-2 font-mono text-sm font-bold text-white"
              >
                {seasons.map((s) => (
                  <option key={s.year} value={s.year}>
                    Temporada {s.year}
                  </option>
                ))}
              </select>
            )}

            {isDetail && seasonRaces && (
              <select
                value={Number(roundParam)}
                onChange={(e) => navigate(`/races/${selectedYear}/${e.target.value}`)}
                aria-label="Selecionar Grande Prêmio"
                className="rounded-xl border border-white/15 bg-[#121622] px-3.5 py-2 text-xs font-bold text-white"
              >
                {seasonRaces.races.map((r) => (
                  <option key={r.round_id} value={r.round_number}>
                    R{r.round_number} · {r.name}
                  </option>
                ))}
              </select>
            )}
          </div>
        </div>
      </section>

      {loading && <div className="h-80 animate-pulse rounded-2xl bg-white/5" />}

      {error && (
        <div className="rounded-xl border border-red-500/40 bg-red-500/10 p-5 text-sm text-red-200">
          {error}
        </div>
      )}

      {/* Season List View */}
      {!loading && !isDetail && seasonRaces && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {seasonRaces.races.map((r) => {
            const ct = circuitTypeMeta(r.circuit_type);
            const CtIcon = ct.icon;
            return (
              <Link
                key={r.round_id}
                to={`/races/${seasonRaces.year}/${r.round_number}`}
                className="group relative rounded-2xl border border-white/10 bg-[#111520] p-5 hover:border-red-500/40 hover:bg-[#151a28] transition-all"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
                      <span className="rounded bg-white/10 px-1.5 py-0.5 font-mono font-bold text-slate-200">
                        R{r.round_number}
                      </span>
                      <span className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] font-semibold ${ct.cls}`}>
                        <CtIcon className="h-3 w-3" /> {ct.label}
                      </span>
                      {r.is_wet_race && (
                        <span className="inline-flex items-center gap-1 rounded border border-sky-400/40 bg-sky-500/20 px-1.5 py-0.5 text-[10px] font-bold text-sky-300">
                          <CloudRain className="h-3 w-3" /> Chuva
                        </span>
                      )}
                    </div>
                    <h2 className="mt-2.5 text-base font-black text-white group-hover:text-red-400 transition-colors">
                      {r.name}
                    </h2>
                    <p className="mt-0.5 flex items-center gap-1.5 text-xs text-slate-400">
                      <CountryFlag country={r.country} size="xs" />
                      <span className="truncate">{r.circuit_name || r.country}</span>
                    </p>
                  </div>
                  {r.date && (
                    <span className="shrink-0 font-mono text-[10px] text-slate-500 flex items-center gap-1">
                      <Calendar className="h-3 w-3" /> {r.date}
                    </span>
                  )}
                </div>

                <div className="mt-4 grid grid-cols-2 gap-2 border-t border-white/5 pt-3 text-xs">
                  <div>
                    <div className="text-[10px] uppercase tracking-wider text-slate-500">Vencedor</div>
                    <div className="mt-0.5 flex items-center gap-1.5 font-bold text-slate-200 truncate">
                      <Trophy className="h-3 w-3 text-amber-400 shrink-0" />
                      <span className="truncate">{r.winner_name ?? '—'}</span>
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase tracking-wider text-slate-500">Destaque FDS</div>
                    <div className="mt-0.5 flex items-center justify-between gap-1 font-bold text-emerald-300 truncate">
                      <span className="inline-flex items-center gap-1 truncate">
                        <Flame className="h-3 w-3 shrink-0" />
                        <span className="truncate">{r.dotw_name ?? '—'}</span>
                      </span>
                      {r.dotw_score !== null && (
                        <span className="font-mono text-white bg-white/10 rounded px-1 py-0 text-[10px]">
                          {r.dotw_score.toFixed(0)}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      )}

      {/* Single Race Detail View */}
      {!loading && isDetail && raceDetail && (
        <>
          {/* Context Metadata Bar */}
          <div className="flex flex-wrap items-center gap-2.5">
            {(() => {
              const ct = circuitTypeMeta(raceDetail.round.circuit_type);
              const CtIcon = ct.icon;
              return (
                <span className={`inline-flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-bold ${ct.cls}`}>
                  <CtIcon className="h-3.5 w-3.5" /> {ct.label}
                </span>
              );
            })()}
            {raceDetail.round.is_wet_race && (
              <span className="inline-flex items-center gap-1.5 rounded-xl border border-sky-400/40 bg-sky-500/20 px-3 py-1.5 text-xs font-bold text-sky-300">
                <CloudRain className="h-3.5 w-3.5" /> Corrida em Pista Molhada
              </span>
            )}
            <span className="rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 font-mono text-xs text-slate-300">
              Tier: {raceDetail.round.data_tier}
            </span>
            {raceDetail.neutralizations.map((n, idx) => (
              <span
                key={`${n.status_type}-${idx}`}
                className="inline-flex items-center gap-1 rounded-xl border border-amber-400/30 bg-amber-500/10 px-2.5 py-1 font-mono text-[11px] font-bold text-amber-300"
              >
                <AlertTriangle className="h-3 w-3" /> {n.status_type} V{n.lap_start}–{n.lap_end}
              </span>
            ))}
          </div>

          {/* Weekend Performance Table */}
          <section className="rounded-2xl border border-white/10 bg-[#111520] overflow-hidden">
            <div className="border-b border-white/10 px-5 py-4">
              <h2 className="text-base font-bold text-white">
                Ranking de Performance Isolada do Fim de Semana (Nota FDS)
              </h2>
              <p className="text-xs text-slate-400">
                Ordenado pelo mérito individual descontando força do carro, tráfego, pneus e neutralizações (incluindo Sprint se houver).
              </p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-white/10 bg-black/30 text-[11px] uppercase tracking-wider text-slate-400">
                  <tr>
                    <th className="px-4 py-3">Nota FDS</th>
                    <th className="px-4 py-3">Piloto</th>
                    <th className="px-3 py-3">Grid → Chegada</th>
                    <th className="px-3 py-3">Status Higiene</th>
                    <th className="px-3 py-3">Δ% Quali</th>
                    <th className="px-3 py-3">Δ% Ritmo</th>
                    <th className="px-3 py-3">Sprint (SQ / SR)</th>
                    <th className="px-3 py-3">Ar Limpo</th>
                    <th className="px-3 py-3 text-right">Ultrapass.</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {raceDetail.drivers.map((d) => (
                    <tr key={d.driver_id} className="hover:bg-white/[0.03]">
                      <td className="px-4 py-3">
                        <OverallBadge score={Math.round(d.weekend_score)} size="sm" />
                      </td>
                      <td className="px-4 py-3">
                        <Link to={`/drivers/${d.reference}`} className="flex items-center gap-2.5 group">
                          <DriverAvatar
                            reference={d.reference}
                            name={d.name}
                            abbreviation={d.abbreviation}
                            teamColor={d.team_color}
                            size="xs"
                          />
                          <div>
                            <div className="flex items-center gap-1.5 font-bold text-white group-hover:text-red-400">
                              <CountryFlag countryCode={d.country_code} nationality={d.nationality} size="xs" />
                              {d.name}
                            </div>
                            <div className="text-[11px] text-slate-400">{d.team_name}</div>
                          </div>
                        </Link>
                      </td>
                      <td className="px-3 py-3 font-mono text-slate-200">
                        P{d.grid ?? '?'} → {d.finish_pos ? `P${d.finish_pos}` : 'DNF'}
                      </td>
                      <td className="px-3 py-3">
                        <span
                          className={`rounded px-2 py-0.5 text-[10px] font-bold ${
                            d.status_category === 'CLEAN_FINISH'
                              ? 'bg-emerald-500/15 text-emerald-300'
                              : d.status_category === 'MECHANICAL_DNF'
                                ? 'bg-sky-500/15 text-sky-300'
                                : 'bg-rose-500/15 text-rose-300'
                          }`}
                        >
                          {d.status_category === 'CLEAN_FINISH'
                            ? 'Limpa'
                            : d.status_category === 'MECHANICAL_DNF'
                              ? 'Mecânico'
                              : d.status_category === 'DRIVER_ERROR'
                                ? 'Erro Piloto'
                                : 'DNS'}
                        </span>
                      </td>
                      <td className="px-3 py-3 font-mono font-bold">
                        {d.quali_teammate_delta_pct !== null ? (
                          <span className={d.quali_teammate_delta_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
                            {d.quali_teammate_delta_pct >= 0 ? '+' : ''}
                            {d.quali_teammate_delta_pct.toFixed(2)}%
                          </span>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td className="px-3 py-3 font-mono font-bold">
                        {d.pace_teammate_delta_pct !== null ? (
                          <span className={d.pace_teammate_delta_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
                            {d.pace_teammate_delta_pct >= 0 ? '+' : ''}
                            {d.pace_teammate_delta_pct.toFixed(2)}%
                          </span>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td className="px-3 py-3 font-mono text-[11px] text-slate-300">
                        {d.sprint_quali_delta_pct !== null || d.sprint_pace_delta_pct !== null ? (
                          <span>
                            {d.sprint_quali_delta_pct !== null ? `Q:${d.sprint_quali_delta_pct >= 0 ? '+' : ''}${d.sprint_quali_delta_pct.toFixed(2)}% ` : ''}
                            {d.sprint_pace_delta_pct !== null ? `R:${d.sprint_pace_delta_pct >= 0 ? '+' : ''}${d.sprint_pace_delta_pct.toFixed(2)}%` : ''}
                          </span>
                        ) : (
                          '—'
                        )}
                      </td>
                      <td className="px-3 py-3 font-mono text-slate-300">
                        {d.clean_air_laps}/{d.clean_laps_total}
                      </td>
                      <td className="px-3 py-3 font-mono text-right text-slate-300">
                        +{d.on_track_overtakes} / -{d.on_track_overtaken}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* Tyre Stints & Lap Time Distribution */}
          {(stintsByDriver.length > 0 || raceDetail.lap_distributions.length > 0) && (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              {stintsByDriver.length > 0 && (
                <section className="rounded-2xl border border-white/10 bg-[#111520] p-5">
                  <h2 className="text-base font-bold text-white">Estratégia de Pneus por Stint</h2>
                  <p className="text-xs text-slate-400 mb-4">
                    Mapeamento volta a volta de compostos usados por cada piloto (OpenF1).
                  </p>
                  <div className="space-y-2.5">
                    {stintsByDriver.map((grp) => (
                      <div key={grp.driver_id} className="flex items-center gap-3 text-xs">
                        <span className="w-14 font-mono font-bold text-slate-200 truncate">
                          {grp.abbreviation || grp.name.split(' ').pop()?.slice(0, 3).toUpperCase()}
                        </span>
                        <div className="relative h-6 flex-1 rounded-lg bg-black/40 overflow-hidden flex">
                          {grp.stints.map((st) => {
                            const widthPct = Math.max(3, ((st.lap_end - st.lap_start + 1) / maxLap) * 100);
                            const cc = compoundColor(st.compound);
                            return (
                              <div
                                key={`${st.driver_id}-${st.stint_number}`}
                                title={`${st.compound} · Voltas ${st.lap_start}–${st.lap_end} (${st.lap_end - st.lap_start + 1}v)`}
                                className="flex h-full items-center justify-center border-r border-[#090B10] font-mono text-[10px] font-black"
                                style={{
                                  width: `${widthPct}%`,
                                  backgroundColor: cc.bg,
                                  color: cc.text,
                                }}
                              >
                                {cc.short}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {raceDetail.lap_distributions.length > 0 && (
                <section className="rounded-2xl border border-white/10 bg-[#111520] p-5">
                  <h2 className="text-base font-bold text-white">Consistência de Ritmo (Voltas Limpas)</h2>
                  <p className="text-xs text-slate-400 mb-4">
                    Intervalo interquartil (Q25–Q75), mediana e variação total das voltas em bandeira verde.
                  </p>
                  <div className="space-y-2.5">
                    {raceDetail.lap_distributions.slice(0, 16).map((ld) => {
                      const span = Math.max(0.5, globalPaceBounds.max - globalPaceBounds.min);
                      const leftQ25 = ((ld.q25_sec - globalPaceBounds.min) / span) * 100;
                      const widthIqr = Math.max(2, ((ld.q75_sec - ld.q25_sec) / span) * 100);
                      const medPos = ((ld.median_sec - globalPaceBounds.min) / span) * 100;
                      return (
                        <div key={ld.driver_id} className="flex items-center gap-3 text-xs">
                          <span className="w-12 font-mono font-bold text-slate-200">
                            {ld.abbreviation}
                          </span>
                          <div className="relative h-5 flex-1 rounded bg-black/40">
                            <div
                              className="absolute top-1.5 h-2 rounded-sm opacity-75"
                              style={{
                                left: `${leftQ25}%`,
                                width: `${widthIqr}%`,
                                backgroundColor: ld.team_color || '#E10600',
                              }}
                              title={`Mediana ${ld.median_sec}s · IQR ${ld.q25_sec}s–${ld.q75_sec}s (${ld.laps_count} voltas)`}
                            />
                            <div
                              className="absolute top-0.5 h-4 w-0.5 bg-white"
                              style={{ left: `${medPos}%` }}
                            />
                          </div>
                          <span className="w-16 text-right font-mono text-[11px] text-slate-400">
                            {ld.median_sec.toFixed(2)}s
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </section>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}
