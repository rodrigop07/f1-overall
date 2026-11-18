import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ArrowUpDown, Calendar, Car, Flag, Flame, ShieldAlert, Sparkles } from 'lucide-react';
import { api } from '../api/client';
import { CountryFlag } from '../components/CountryFlag';
import { DriverAvatar } from '../components/DriverAvatar';
import { dataTierLabel, DriverCard } from '../components/DriverCard';
import { OverallBadge } from '../components/OverallBadge';
import type { SeasonDriverRating, SeasonMeta, SeasonRankingsResponse } from '../types/f1';

type SortKey =
  | 'overall_raw'
  | 'pace_ovr'
  | 'quali_ovr'
  | 'consistency_ovr'
  | 'racecraft_ovr'
  | 'experience_ovr'
  | 'car_rating'
  | 'car_delta';

const FEATURED_SEASONS = [2026, 2025, 2024, 2021, 2012, 2007, 2004, 1994, 1988, 1976, 1965, 1955];

export function SeasonRankingsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const yearParam = searchParams.get('year');
  const parsedYear = yearParam ? Number(yearParam) : null;

  const [mode, setMode] = useState<'current' | 'season'>(
    parsedYear && !Number.isNaN(parsedYear) ? 'season' : 'current'
  );
  const [selectedYear, setSelectedYear] = useState<number>(
    parsedYear && !Number.isNaN(parsedYear) ? parsedYear : 2026
  );
  const [seasons, setSeasons] = useState<SeasonMeta[]>([]);
  const [data, setData] = useState<SeasonRankingsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [teamFilter, setTeamFilter] = useState<string>('ALL');
  const [sortKey, setSortKey] = useState<SortKey>('overall_raw');
  const [sortAsc, setSortAsc] = useState(false);

  useEffect(() => {
    if (parsedYear && !Number.isNaN(parsedYear)) {
      setMode('season');
      setSelectedYear(parsedYear);
    }
  }, [parsedYear]);

  useEffect(() => {
    api.getSeasons().then((res) => {
      setSeasons(res.seasons);
      if (res.seasons.length > 0 && !(parsedYear && !Number.isNaN(parsedYear))) {
        setSelectedYear(res.seasons[0].year);
      }
    }).catch(() => {});
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    const req = mode === 'current' ? api.getCurrentRankings() : api.getSeasonRankings(selectedYear);
    req
      .then((res) => {
        if (!cancelled) {
          setData(res);
          setTeamFilter('ALL');
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Erro ao carregar ranking');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [mode, selectedYear]);

  const teams = useMemo(() => {
    if (!data) return [];
    return Array.from(new Set(data.drivers.map((d) => d.team_name))).sort();
  }, [data]);

  const filteredDrivers = useMemo(() => {
    if (!data) return [];
    const list =
      teamFilter === 'ALL' ? data.drivers : data.drivers.filter((d) => d.team_name === teamFilter);
    return [...list].sort((a: SeasonDriverRating, b: SeasonDriverRating) => {
      const va = a[sortKey];
      const vb = b[sortKey];
      return sortAsc ? va - vb : vb - va;
    });
  }, [data, teamFilter, sortKey, sortAsc]);

  const top3 = useMemo(() => (data ? data.drivers.slice(0, 3) : []), [data]);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(false);
    }
  };

  return (
    <div className="space-y-8">
      {/* Header & Mode Switch */}
      <section className="rounded-2xl border border-white/10 bg-gradient-to-br from-[#131826] via-[#0e121c] to-[#090B10] p-6">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-[#E10600]/40 bg-[#E10600]/10 px-3 py-1 text-[11px] font-bold uppercase tracking-wider text-red-300">
              <Sparkles className="h-3.5 w-3.5" /> Calibração em Rede LMM + 5 Pilares
            </div>
            <h1 className="mt-3 text-2xl font-black tracking-tight text-white sm:text-3xl">
              {mode === 'current'
                ? `Power Ranking Atual (${data?.year ?? selectedYear})`
                : `Temporada ${selectedYear} — Isolamento Piloto vs. Carro`}
            </h1>
            <p className="mt-1.5 max-w-2xl text-sm text-slate-400">
              {mode === 'current'
                ? 'Forma recente com decaimento exponencial (meia-vida H=16 GPs) e Bayesian Shrinkage (m=10 GPs) sobre a escala ancorada 0–99 (média do grid = 82).'
                : `Avaliação completa do grid da temporada ${selectedYear}, separando a performance da equipe da habilidade pura do piloto.`}
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="inline-flex rounded-xl border border-white/10 bg-black/40 p-1">
              <button
                type="button"
                onClick={() => {
                  setMode('current');
                  setSearchParams({});
                }}
                className={`inline-flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-xs font-bold transition ${
                  mode === 'current'
                    ? 'bg-[#E10600] text-white'
                    : 'text-slate-300 hover:text-white'
                }`}
              >
                <Flame className="h-3.5 w-3.5" /> Overall Atual
              </button>
              <button
                type="button"
                onClick={() => setMode('season')}
                className={`inline-flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-xs font-bold transition ${
                  mode === 'season'
                    ? 'bg-[#E10600] text-white'
                    : 'text-slate-300 hover:text-white'
                }`}
              >
                <Calendar className="h-3.5 w-3.5" /> Por Temporada
              </button>
            </div>

            {mode === 'season' && (
              <select
                value={selectedYear}
                onChange={(e) => {
                  const yr = Number(e.target.value);
                  setSelectedYear(yr);
                  setSearchParams({ year: String(yr) });
                }}
                aria-label="Selecionar temporada"
                className="rounded-xl border border-white/15 bg-[#121622] px-3.5 py-2 font-mono text-sm font-bold text-white focus:border-[#E10600] focus:outline-none"
              >
                {seasons.map((s) => (
                  <option key={s.year} value={s.year}>
                    Temporada {s.year} ({s.driver_count} pilotos)
                  </option>
                ))}
              </select>
            )}
          </div>
        </div>

        {/* Quick season jump chips */}
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-white/5 pt-4">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="mr-1 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              Atalhos de Era:
            </span>
            {FEATURED_SEASONS.map((yr) => (
              <button
                key={yr}
                type="button"
                onClick={() => {
                  setMode('season');
                  setSelectedYear(yr);
                  setSearchParams({ year: String(yr) });
                }}
                className={`rounded-md px-2.5 py-1 font-mono text-xs font-semibold transition ${
                  mode === 'season' && selectedYear === yr
                    ? 'bg-white text-black'
                    : 'bg-white/5 text-slate-300 hover:bg-white/10'
                }`}
              >
                {yr}
              </button>
            ))}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Link
              to={`/races?year=${data?.year ?? selectedYear}`}
              className="inline-flex items-center gap-1.5 rounded-lg border border-white/15 bg-white/5 px-3 py-1.5 text-xs font-semibold text-slate-200 hover:bg-white/10 hover:text-white transition"
            >
              <Flag className="h-3.5 w-3.5 text-red-400" />
              GPs de {data?.year ?? selectedYear}
            </Link>
            <Link
              to={`/what-if?year=${data?.year ?? selectedYear}`}
              className="inline-flex items-center gap-1.5 rounded-lg border border-amber-400/30 bg-amber-500/10 px-3 py-1.5 text-xs font-semibold text-amber-200 hover:bg-amber-500/20 transition"
            >
              <Sparkles className="h-3.5 w-3.5 text-amber-400" />
              E se Carros Iguais ({data?.year ?? selectedYear})?
            </Link>
          </div>
        </div>
      </section>

      {loading && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          {[1, 2, 3].map((k) => (
            <div key={k} className="h-52 animate-pulse rounded-2xl bg-white/5" />
          ))}
        </div>
      )}

      {error && (
        <div className="rounded-xl border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-200">
          Erro ao carregar dados: {error}
        </div>
      )}

      {!loading && data && (
        <>
          {/* Top 3 Podium Cards */}
          <section>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-sm font-bold uppercase tracking-wider text-slate-400">
                Pódio do Modelo — {data.year} ({data.rounds_analyzed} GPs analisados)
              </h2>
              <span className="text-xs text-slate-500">
                Clique em qualquer piloto para auditoria completa
              </span>
            </div>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              {top3.map((d) => (
                <DriverCard
                  key={d.driver_id}
                  rank={d.rank}
                  reference={d.reference}
                  name={d.name}
                  abbreviation={d.abbreviation}
                  nationality={d.nationality}
                  countryCode={d.country_code}
                  teamName={d.team_name}
                  teamColor={d.team_color}
                  overall={d.overall}
                  overallRaw={d.overall_raw}
                  overallCi={d.overall_ci}
                  badges={d.badges}
                  pace={d.pace_ovr}
                  qualifying={d.quali_ovr}
                  consistency={d.consistency_ovr}
                  racecraft={d.racecraft_ovr}
                  experience={d.experience_ovr}
                  racesCount={d.races_count}
                  carRating={d.car_rating}
                  shrinkageWeight={d.shrinkage_weight}
                  subtitle={dataTierLabel(d.data_tier)}
                />
              ))}
            </div>
          </section>

          {/* Main Grid Table + Car Strength Sidebar */}
          <div className="grid grid-cols-1 gap-6 xl:grid-cols-4">
            <section className="xl:col-span-3 rounded-2xl border border-white/10 bg-[#111520] overflow-hidden">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/10 px-5 py-4">
                <div>
                  <h2 className="text-base font-bold text-white">Classificação Completa do Grid</h2>
                  <p className="text-xs text-slate-400">
                    {filteredDrivers.length} pilotos · Ordenado por <span className="font-mono text-slate-200">{sortKey}</span>
                  </p>
                </div>
                <select
                  value={teamFilter}
                  onChange={(e) => setTeamFilter(e.target.value)}
                  aria-label="Filtrar por equipe"
                  className="rounded-lg border border-white/10 bg-[#0b0e16] px-3 py-1.5 text-xs text-slate-200 focus:border-[#E10600] focus:outline-none"
                >
                  <option value="ALL">Todas as equipes</option>
                  {teams.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-white/10 bg-black/30 text-[11px] uppercase tracking-wider text-slate-400">
                    <tr>
                      <th className="px-4 py-3 font-semibold">#</th>
                      <th className="px-4 py-3 font-semibold">Piloto</th>
                      <th className="px-3 py-3 font-semibold cursor-pointer hover:text-white" onClick={() => handleSort('overall_raw')}>
                        <span className="inline-flex items-center gap-1">OVR <ArrowUpDown className="h-3 w-3" /></span>
                      </th>
                      <th className="px-3 py-3 font-semibold cursor-pointer hover:text-white" onClick={() => handleSort('pace_ovr')}>RIT</th>
                      <th className="px-3 py-3 font-semibold cursor-pointer hover:text-white" onClick={() => handleSort('quali_ovr')}>CLA</th>
                      <th className="px-3 py-3 font-semibold cursor-pointer hover:text-white" onClick={() => handleSort('consistency_ovr')}>CON</th>
                      <th className="px-3 py-3 font-semibold cursor-pointer hover:text-white" onClick={() => handleSort('racecraft_ovr')}>CMB</th>
                      <th className="px-3 py-3 font-semibold cursor-pointer hover:text-white" onClick={() => handleSort('experience_ovr')}>EXP</th>
                      <th className="px-3 py-3 font-semibold cursor-pointer hover:text-white" onClick={() => handleSort('car_rating')}>Carro</th>
                      <th className="px-3 py-3 font-semibold cursor-pointer hover:text-white" onClick={() => handleSort('car_delta')}>Δ Carro</th>
                      <th className="px-3 py-3 font-semibold text-right">GPs</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-white/5">
                    {filteredDrivers.map((d, idx) => (
                      <tr key={d.driver_id} className="hover:bg-white/[0.03] transition-colors">
                        <td className="px-4 py-3 font-mono font-bold text-slate-400 tabular-nums">
                          {sortKey === 'overall_raw' && !sortAsc && teamFilter === 'ALL' ? d.rank : idx + 1}
                        </td>
                        <td className="px-4 py-3">
                          <Link
                            to={`/drivers/${d.reference}`}
                            className="flex items-center gap-2.5 group"
                          >
                            <DriverAvatar
                              reference={d.reference}
                              name={d.name}
                              abbreviation={d.abbreviation}
                              teamColor={d.team_color}
                              size="xs"
                            />
                            <div className="min-w-0">
                              <div className="flex items-center gap-1.5 font-bold text-white group-hover:text-red-400 transition-colors">
                                <CountryFlag countryCode={d.country_code} nationality={d.nationality} size="xs" />
                                <span className="truncate">{d.name}</span>
                                {d.shrinkage_weight < 0.7 && (
                                  <span
                                    title={`Amostra reduzida: Bayesian Shrinkage ativo (${(d.shrinkage_weight * 100).toFixed(0)}% peso observado)`}
                                    className="text-amber-300"
                                  >
                                    <ShieldAlert className="h-3.5 w-3.5" />
                                  </span>
                                )}
                              </div>
                              <div className="flex items-center gap-1.5 text-[11px] text-slate-400">
                                <span>{d.team_name}</span>
                                {d.badges?.[0] && (
                                  <span className="hidden sm:inline rounded bg-amber-500/10 px-1.5 py-0 text-[9px] font-semibold text-amber-300 border border-amber-400/20">
                                    {d.badges[0]}
                                  </span>
                                )}
                              </div>
                            </div>
                          </Link>
                        </td>
                        <td className="px-3 py-3">
                          <div className="flex items-center gap-2">
                            <OverallBadge score={d.overall} size="sm" />
                            <div className="flex flex-col leading-tight">
                              <span className="font-mono text-[10px] text-slate-500">
                                ±{d.overall_ci.toFixed(1)}
                              </span>
                              {d.delta_vs_prev !== null && (
                                <span
                                  className={`font-mono text-[10px] font-bold ${
                                    d.delta_vs_prev >= 0 ? 'text-emerald-400' : 'text-rose-400'
                                  }`}
                                >
                                  {d.delta_vs_prev >= 0 ? `+${d.delta_vs_prev.toFixed(1)}` : d.delta_vs_prev.toFixed(1)}
                                </span>
                              )}
                            </div>
                          </div>
                        </td>
                        <td className="px-3 py-3 font-mono font-semibold text-slate-200 tabular-nums">{d.pace_ovr.toFixed(1)}</td>
                        <td className="px-3 py-3 font-mono font-semibold text-slate-200 tabular-nums">{d.quali_ovr.toFixed(1)}</td>
                        <td className="px-3 py-3 font-mono font-semibold text-slate-200 tabular-nums">{d.consistency_ovr.toFixed(1)}</td>
                        <td className="px-3 py-3 font-mono font-semibold text-slate-200 tabular-nums">{d.racecraft_ovr.toFixed(1)}</td>
                        <td className="px-3 py-3 font-mono font-semibold text-slate-400 tabular-nums">{d.experience_ovr.toFixed(1)}</td>
                        <td className="px-3 py-3 font-mono text-slate-300 tabular-nums">{d.car_rating.toFixed(1)}</td>
                        <td className="px-3 py-3 font-mono font-bold tabular-nums">
                          <span className={d.car_delta >= 0 ? 'text-emerald-400' : 'text-amber-400'}>
                            {d.car_delta >= 0 ? `+${d.car_delta.toFixed(1)}` : d.car_delta.toFixed(1)}
                          </span>
                        </td>
                        <td className="px-3 py-3 font-mono text-right text-slate-400 tabular-nums">{d.races_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            {/* Car Performance Sidebar */}
            <aside className="rounded-2xl border border-white/10 bg-[#111520] p-5 h-fit">
              <div className="flex items-center gap-2 text-white font-bold">
                <Car className="h-4 w-4 text-[#E10600]" />
                <h2>Índice dos Carros ({data.year})</h2>
              </div>
              <p className="mt-1 text-xs text-slate-400">
                Força isolada de cada chassi/motor estimada pelo modelo LMM (escala 60–99).
              </p>
              <div className="mt-4 space-y-2.5">
                {data.cars.map((c, idx) => {
                  const pct = Math.max(4, Math.min(100, ((c.car_rating - 60) / 39) * 100));
                  return (
                    <div key={c.team_id} className="space-y-1">
                      <div className="flex items-center justify-between text-xs">
                        <span className="truncate font-medium text-slate-200">
                          <span className="font-mono text-slate-500 mr-1.5">{idx + 1}.</span>
                          {c.team_name}
                        </span>
                        <span className="font-mono font-bold text-white tabular-nums">
                          {c.car_rating.toFixed(1)}
                        </span>
                      </div>
                      <div className="h-1.5 w-full rounded-full bg-slate-800 overflow-hidden">
                        <div
                          className="h-full rounded-full"
                          style={{ width: `${pct}%`, backgroundColor: c.team_color || '#64748b' }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </aside>
          </div>
        </>
      )}
    </div>
  );
}
