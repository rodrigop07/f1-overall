import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ArrowRightLeft, Award, Scale, Sparkles, Trophy, Zap } from 'lucide-react';
import { api } from '../api/client';
import { DriverAvatar } from '../components/DriverAvatar';
import { OverallBadge } from '../components/OverallBadge';
import type {
  CarSeasonRating,
  DriverSummary,
  EqualMachineryResponse,
  SeasonMeta,
  SeatSwapResponse,
} from '../types/f1';

export function WhatIfPage() {
  const [searchParams] = useSearchParams();
  const yrParam = Number(searchParams.get('year'));
  const initYear = yrParam && !Number.isNaN(yrParam) ? yrParam : 2021;

  const [tab, setTab] = useState<'equal' | 'swap'>('equal');
  const [seasons, setSeasons] = useState<SeasonMeta[]>([]);
  const [allDrivers, setAllDrivers] = useState<DriverSummary[]>([]);

  // Tab 1: Equal Machinery
  const [equalYear, setEqualYear] = useState<number>(initYear);
  const [excludeMechDnf, setExcludeMechDnf] = useState(true);
  const [equalData, setEqualData] = useState<EqualMachineryResponse | null>(null);
  const [equalLoading, setEqualLoading] = useState(false);

  // Tab 2: Seat Swap Monte Carlo
  const [swapYear, setSwapYear] = useState<number>(initYear);
  const [swapDriverRef, setSwapDriverRef] = useState<string>('alonso');
  const [driverQuery, setDriverQuery] = useState('');
  const [seasonCars, setSeasonCars] = useState<CarSeasonRating[]>([]);
  const [targetTeamId, setTargetTeamId] = useState<number>(0);
  const [nSims, setNSims] = useState<number>(500);
  const [swapData, setSwapData] = useState<SeatSwapResponse | null>(null);
  const [swapLoading, setSwapLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getSeasons().then((res) => setSeasons(res.seasons)).catch(() => {});
    api.getDriversList().then((res) => setAllDrivers(res.drivers)).catch(() => {});
  }, []);

  useEffect(() => {
    if (tab !== 'equal') return;
    let cancelled = false;
    setEqualLoading(true);
    setError(null);
    api
      .getEqualMachinery(equalYear, excludeMechDnf)
      .then((res) => {
        if (!cancelled) setEqualData(res);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Erro ao simular temporada');
      })
      .finally(() => {
        if (!cancelled) setEqualLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [tab, equalYear, excludeMechDnf]);

  useEffect(() => {
    api
      .getSeasonRankings(swapYear)
      .then((res) => {
        setSeasonCars(res.cars);
        if (res.cars.length > 0) {
          setTargetTeamId((prev) =>
            res.cars.some((c) => c.team_id === prev) ? prev : res.cars[0].team_id
          );
        }
      })
      .catch(() => {});
  }, [swapYear]);

  const filteredDrivers = useMemo(() => {
    const q = driverQuery.trim().toLowerCase();
    const list = q
      ? allDrivers.filter((d) => d.name.toLowerCase().includes(q) || d.reference.includes(q))
      : allDrivers;
    return list.slice(0, 60);
  }, [allDrivers, driverQuery]);

  const runSeatSwap = () => {
    if (!targetTeamId || !swapDriverRef) return;
    setSwapLoading(true);
    setError(null);
    api
      .simulateSeatSwap({
        driver_ref: swapDriverRef,
        target_team_id: targetTeamId,
        year: swapYear,
        n_sims: nSims,
      })
      .then((res) => setSwapData(res))
      .catch((err) => setError(err instanceof Error ? err.message : 'Erro ao simular troca de assento'))
      .finally(() => setSwapLoading(false));
  };

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-white/10 bg-gradient-to-br from-[#141927] via-[#0e121c] to-[#090B10] p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-amber-400/40 bg-amber-500/10 px-3 py-1 text-[11px] font-bold uppercase tracking-wider text-amber-300">
              <Sparkles className="h-3.5 w-3.5" /> Laboratório Contrafactual
            </div>
            <h1 className="mt-2 text-2xl font-black tracking-tight text-white sm:text-3xl">
              Simulador &ldquo;E se...?&rdquo; (Carros Iguais &amp; Troca de Assento)
            </h1>
            <p className="mt-1 text-sm text-slate-400">
              Recalcule campeonatos mundiais removendo a diferença entre carros ou simule 500 temporadas em Monte Carlo colocando qualquer piloto em outro carro.
            </p>
          </div>

          <div className="inline-flex rounded-xl border border-white/10 bg-black/40 p-1">
            <button
              type="button"
              onClick={() => setTab('equal')}
              className={`inline-flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-xs font-bold transition ${
                tab === 'equal' ? 'bg-[#E10600] text-white' : 'text-slate-300 hover:text-white'
              }`}
            >
              <Scale className="h-3.5 w-3.5" /> Carros Iguais
            </button>
            <button
              type="button"
              onClick={() => setTab('swap')}
              className={`inline-flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-xs font-bold transition ${
                tab === 'swap' ? 'bg-[#E10600] text-white' : 'text-slate-300 hover:text-white'
              }`}
            >
              <ArrowRightLeft className="h-3.5 w-3.5" /> Troca de Assento (Monte Carlo)
            </button>
          </div>
        </div>
      </section>

      {error && (
        <div className="rounded-xl border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-200">
          {error}
        </div>
      )}

      {/* TAB 1: Equal Machinery */}
      {tab === 'equal' && (
        <div className="space-y-6">
          <section className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-white/10 bg-[#111520] p-5">
            <div className="flex flex-wrap items-center gap-3">
              <label className="text-xs font-bold text-slate-300">Temporada:</label>
              <select
                value={equalYear}
                onChange={(e) => setEqualYear(Number(e.target.value))}
                aria-label="Selecionar temporada em carros iguais"
                className="rounded-xl border border-white/15 bg-[#090B10] px-3.5 py-2 font-mono text-sm font-bold text-white"
              >
                {seasons.map((s) => (
                  <option key={s.year} value={s.year}>
                    {s.year}
                  </option>
                ))}
              </select>
              <div className="hidden sm:flex gap-1.5">
                {[2026, 2024, 2021, 2012, 2008, 1994, 1988].map((yr) => (
                  <button
                    key={yr}
                    type="button"
                    onClick={() => setEqualYear(yr)}
                    className={`rounded-md px-2.5 py-1 font-mono text-xs font-semibold ${
                      equalYear === yr ? 'bg-white text-black' : 'bg-white/5 text-slate-300 hover:bg-white/10'
                    }`}
                  >
                    {yr}
                  </button>
                ))}
              </div>
            </div>

            <label className="inline-flex cursor-pointer items-center gap-2 text-xs font-semibold text-slate-300">
              <input
                type="checkbox"
                checked={excludeMechDnf}
                onChange={(e) => setExcludeMechDnf(e.target.checked)}
                className="h-4 w-4 accent-[#E10600]"
              />
              Neutralizar DNFs mecânicos (estimativa pura de ritmo quando o carro quebrou)
            </label>
          </section>

          {equalLoading && <div className="h-72 animate-pulse rounded-2xl bg-white/5" />}

          {!equalLoading && equalData && (
            <>
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                {equalData.actual_champion && (
                  <div className="rounded-2xl border border-white/10 bg-[#111520] p-5">
                    <div className="text-xs font-bold uppercase tracking-wider text-slate-400">
                      Campeão Real da Pista ({equalData.year})
                    </div>
                    <div className="mt-2 flex items-center justify-between">
                      <div>
                        <div className="text-2xl font-black text-white">
                          {equalData.actual_champion.name}
                        </div>
                        <div className="text-xs text-slate-400">
                          {equalData.actual_champion.team_name} · {equalData.actual_champion.actual_wins} vitórias
                        </div>
                      </div>
                      <div className="text-right font-mono">
                        <div className="text-2xl font-black text-slate-200">
                          {equalData.actual_champion.actual_points}
                        </div>
                        <div className="text-[10px] text-slate-500">PTS REAIS</div>
                      </div>
                    </div>
                  </div>
                )}

                {equalData.equal_champion && (
                  <div className="rounded-2xl border border-amber-400/40 bg-amber-500/10 p-5">
                    <div className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wider text-amber-300">
                      <Trophy className="h-3.5 w-3.5" /> Campeão em Carros Iguais ({equalData.year})
                    </div>
                    <div className="mt-2 flex items-center justify-between">
                      <div>
                        <div className="text-2xl font-black text-white">
                          {equalData.equal_champion.name}
                        </div>
                        <div className="text-xs text-amber-200/80">
                          {equalData.equal_champion.team_name} · {equalData.equal_champion.equal_wins} vitórias virtuais
                        </div>
                      </div>
                      <div className="text-right font-mono">
                        <div className="text-2xl font-black text-amber-300">
                          {equalData.equal_champion.equal_points}
                        </div>
                        <div className="text-[10px] text-amber-200/70">PTS IGUAIS</div>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              <section className="rounded-2xl border border-white/10 bg-[#111520] overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="border-b border-white/10 bg-black/30 text-[11px] uppercase tracking-wider text-slate-400">
                      <tr>
                        <th className="px-4 py-3">Pos Igual</th>
                        <th className="px-4 py-3">Piloto</th>
                        <th className="px-3 py-3">Pts Iguais</th>
                        <th className="px-3 py-3">Vitórias (Igual)</th>
                        <th className="px-3 py-3">Pódios (Igual)</th>
                        <th className="px-3 py-3">Pos Real</th>
                        <th className="px-3 py-3">Pts Reais</th>
                        <th className="px-3 py-3 text-right">Saldo Pos.</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                      {equalData.standings.map((row) => (
                        <tr key={row.driver_id} className="hover:bg-white/[0.03]">
                          <td className="px-4 py-3 font-mono font-black text-white">
                            {row.equal_pos}º
                          </td>
                          <td className="px-4 py-3">
                            <Link to={`/drivers/${row.reference}`} className="flex items-center gap-2.5 group">
                              <DriverAvatar
                                reference={row.reference}
                                name={row.name}
                                teamColor={row.team_color}
                                size="xs"
                              />
                              <div>
                                <div className="font-bold text-white group-hover:text-red-400">
                                  {row.name}
                                </div>
                                <div className="text-[11px] text-slate-400">{row.team_name}</div>
                              </div>
                            </Link>
                          </td>
                          <td className="px-3 py-3 font-mono font-bold text-amber-300">
                            {row.equal_points}
                          </td>
                          <td className="px-3 py-3 font-mono text-slate-200">{row.equal_wins}</td>
                          <td className="px-3 py-3 font-mono text-slate-300">{row.equal_podiums}</td>
                          <td className="px-3 py-3 font-mono text-slate-400">{row.actual_pos}º</td>
                          <td className="px-3 py-3 font-mono text-slate-400">{row.actual_points}</td>
                          <td className="px-3 py-3 font-mono font-bold text-right">
                            {row.pos_delta > 0 ? (
                              <span className="rounded bg-emerald-500/15 px-2 py-0.5 text-emerald-300">
                                +{row.pos_delta}
                              </span>
                            ) : row.pos_delta < 0 ? (
                              <span className="rounded bg-rose-500/15 px-2 py-0.5 text-rose-300">
                                {row.pos_delta}
                              </span>
                            ) : (
                              <span className="text-slate-500">=</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </>
          )}
        </div>
      )}

      {/* TAB 2: Seat Swap Monte Carlo */}
      {tab === 'swap' && (
        <div className="space-y-6">
          <section className="rounded-2xl border border-white/10 bg-[#111520] p-5 grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-5 items-end">
            <div className="lg:col-span-2 space-y-1.5">
              <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                Piloto para Transferir (Qualquer Era)
              </label>
              <input
                value={driverQuery}
                onChange={(e) => setDriverQuery(e.target.value)}
                placeholder="Filtrar piloto (ex: Senna, Alonso, Leclerc)..."
                className="w-full rounded-lg border border-white/10 bg-[#090B10] px-3 py-1.5 text-xs text-white"
              />
              <select
                value={swapDriverRef}
                onChange={(e) => setSwapDriverRef(e.target.value)}
                aria-label="Selecionar piloto"
                className="w-full rounded-lg border border-white/15 bg-[#121622] px-3 py-2 text-xs font-bold text-white"
              >
                {filteredDrivers.map((d) => (
                  <option key={d.driver_id} value={d.reference}>
                    {d.name} ({d.first_year}–{d.last_year}) · OVR {d.overall}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                Temporada Alvo
              </label>
              <select
                value={swapYear}
                onChange={(e) => setSwapYear(Number(e.target.value))}
                aria-label="Selecionar temporada alvo"
                className="w-full rounded-lg border border-white/15 bg-[#121622] px-3 py-2 font-mono text-xs font-bold text-white"
              >
                {seasons.map((s) => (
                  <option key={s.year} value={s.year}>
                    {s.year}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                Carro / Equipe em {swapYear}
              </label>
              <select
                value={targetTeamId}
                onChange={(e) => setTargetTeamId(Number(e.target.value))}
                aria-label="Selecionar equipe destino"
                className="w-full rounded-lg border border-white/15 bg-[#121622] px-3 py-2 text-xs font-bold text-white"
              >
                {seasonCars.map((c) => (
                  <option key={c.team_id} value={c.team_id}>
                    {c.team_name} (Carro {c.car_rating.toFixed(1)})
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1.5">
              <select
                value={nSims}
                onChange={(e) => setNSims(Number(e.target.value))}
                aria-label="Número de simulações"
                className="w-full rounded-lg border border-white/10 bg-[#090B10] px-3 py-1.5 font-mono text-xs text-slate-300"
              >
                <option value={500}>500 simulações</option>
                <option value={1000}>1000 simulações</option>
              </select>
              <button
                type="button"
                onClick={runSeatSwap}
                disabled={swapLoading}
                className="w-full inline-flex items-center justify-center gap-1.5 rounded-xl bg-[#E10600] px-4 py-2 text-xs font-black text-white hover:bg-red-600 transition cursor-pointer disabled:opacity-50"
              >
                <Zap className="h-3.5 w-3.5" />
                {swapLoading ? 'Simulando...' : 'Simular Troca'}
              </button>
            </div>
          </section>

          {swapData && (
            <>
              <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
                <div className="rounded-2xl border border-amber-400/40 bg-amber-500/10 p-4">
                  <div className="text-[11px] font-bold uppercase text-amber-300">
                    Chance de Título (WDC)
                  </div>
                  <div className="mt-1 font-mono text-3xl font-black text-white">
                    {swapData.driver.title_prob_pct.toFixed(1)}%
                  </div>
                  <div className="text-xs text-slate-300 mt-1">
                    {swapData.driver.name} na {swapData.target_team.team_name} ({swapData.year})
                  </div>
                </div>
                <div className="rounded-2xl border border-white/10 bg-[#111520] p-4">
                  <div className="text-[11px] font-bold uppercase text-slate-400">Pontos Esperados</div>
                  <div className="mt-1 font-mono text-3xl font-black text-white">
                    {swapData.driver.expected_points.toFixed(1)}
                  </div>
                  <div className="text-xs text-slate-400 mt-1">
                    Posição média: #{swapData.driver.expected_pos.toFixed(1)}
                  </div>
                </div>
                <div className="rounded-2xl border border-white/10 bg-[#111520] p-4">
                  <div className="text-[11px] font-bold uppercase text-slate-400">Vitórias & Pódios Médios</div>
                  <div className="mt-1 font-mono text-3xl font-black text-emerald-300">
                    {swapData.driver.expected_wins.toFixed(1)}V · {swapData.driver.expected_podiums.toFixed(1)}P
                  </div>
                  <div className="text-xs text-slate-400 mt-1">
                    Substituiu {swapData.replaced_driver}
                  </div>
                </div>
                <div className="rounded-2xl border border-white/10 bg-[#111520] p-4">
                  <div className="text-[11px] font-bold uppercase text-slate-400">
                    Bater Companheiro
                  </div>
                  <div className="mt-1 font-mono text-3xl font-black text-sky-300">
                    {swapData.teammate_beat_pct !== null ? `${swapData.teammate_beat_pct.toFixed(1)}%` : '—'}
                  </div>
                  <div className="text-xs text-slate-400 mt-1">
                    {swapData.teammate ? `vs ${swapData.teammate.name}` : 'Sem companheiro'}
                  </div>
                </div>
              </div>

              <section className="rounded-2xl border border-white/10 bg-[#111520] overflow-hidden">
                <div className="border-b border-white/10 px-5 py-4 flex items-center gap-2">
                  <Award className="h-4 w-4 text-amber-400" />
                  <h2 className="text-base font-bold text-white">
                    Classificação Projetada ({swapData.n_simulations} Temporadas Monte Carlo)
                  </h2>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="border-b border-white/10 bg-black/30 text-[11px] uppercase tracking-wider text-slate-400">
                      <tr>
                        <th className="px-4 py-3">#</th>
                        <th className="px-4 py-3">Piloto</th>
                        <th className="px-3 py-3">OVR</th>
                        <th className="px-3 py-3">Pts Médios</th>
                        <th className="px-3 py-3">Vitórias Médias</th>
                        <th className="px-3 py-3">Pódios Médios</th>
                        <th className="px-3 py-3 text-right">Prob. Título</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                      {swapData.standings.map((row) => (
                        <tr
                          key={`${row.driver_id}-${row.team_name}`}
                          className={
                            row.is_swapped_driver
                              ? 'bg-[#E10600]/15'
                              : row.is_teammate
                                ? 'bg-sky-500/10'
                                : 'hover:bg-white/[0.03]'
                          }
                        >
                          <td className="px-4 py-3 font-mono font-bold text-slate-300">
                            {row.projected_rank}º
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-2">
                              <span
                                className="h-5 w-1 rounded-full"
                                style={{ backgroundColor: row.team_color || '#64748B' }}
                              />
                              <div>
                                <div className="flex items-center gap-1.5 font-bold text-white">
                                  <span>{row.name}</span>
                                  {row.is_swapped_driver && (
                                    <span className="rounded bg-[#E10600] px-1.5 py-0 text-[9px] font-bold text-white">
                                      NOVO ASSENTO
                                    </span>
                                  )}
                                  {row.is_teammate && (
                                    <span className="rounded bg-sky-500/20 px-1.5 py-0 text-[9px] font-bold text-sky-300">
                                      COMPANHEIRO
                                    </span>
                                  )}
                                </div>
                                <div className="text-[11px] text-slate-400">{row.team_name}</div>
                              </div>
                            </div>
                          </td>
                          <td className="px-3 py-3">
                            <OverallBadge score={row.overall} size="sm" />
                          </td>
                          <td className="px-3 py-3 font-mono font-bold text-white">
                            {row.expected_points.toFixed(1)}
                          </td>
                          <td className="px-3 py-3 font-mono text-slate-300">
                            {row.expected_wins.toFixed(2)}
                          </td>
                          <td className="px-3 py-3 font-mono text-slate-300">
                            {row.expected_podiums.toFixed(2)}
                          </td>
                          <td className="px-3 py-3 font-mono text-right font-bold text-amber-300">
                            {row.title_prob_pct.toFixed(1)}%
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            </>
          )}
        </div>
      )}
    </div>
  );
}
