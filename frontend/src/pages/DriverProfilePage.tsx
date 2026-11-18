import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  Award,
  CheckCircle2,
  GitCompareArrows,
  ShieldCheck,
  TriangleAlert,
  Wrench,
} from 'lucide-react';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { api } from '../api/client';
import { OverallBadge } from '../components/OverallBadge';
import { PillarBars } from '../components/PillarBars';
import { PillarRadar } from '../components/PillarRadar';
import type { DriverProfileResponse } from '../types/f1';

export function DriverProfilePage() {
  const { driverRef } = useParams<{ driverRef: string }>();
  const [data, setData] = useState<DriverProfileResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [viewScope, setViewScope] = useState<'alltime' | 'current'>('alltime');

  useEffect(() => {
    if (!driverRef) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .getDriverProfile(driverRef)
      .then((res) => {
        if (!cancelled) {
          setData(res);
          setViewScope(res.current_rating ? 'current' : 'alltime');
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Piloto não encontrado');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [driverRef]);

  if (loading) {
    return <div className="h-96 animate-pulse rounded-2xl bg-white/5" />;
  }

  if (error || !data) {
    return (
      <div className="rounded-2xl border border-red-500/40 bg-red-500/10 p-6 text-red-200">
        {error || 'Piloto não encontrado'}
      </div>
    );
  }

  const { driver, current_rating, seasons, teammates, hygiene_summary, recent_races } = data;
  const active = viewScope === 'current' && current_rating ? current_rating : driver;
  const teamColor =
    viewScope === 'current' && current_rating
      ? current_rating.team_color
      : driver.primary_team_color;

  const progressionData = seasons.map((s) => ({
    year: s.year,
    piloto: Number(s.overall_raw.toFixed(1)),
    carro: Number(s.car_rating.toFixed(1)),
    equipe: s.team_name,
  }));

  return (
    <div className="space-y-6">
      {/* Hero Profile Banner */}
      <section className="relative overflow-hidden rounded-2xl border border-white/10 bg-[#111520] p-6">
        <div
          className="absolute inset-x-0 top-0 h-1.5"
          style={{ backgroundColor: teamColor || '#E10600' }}
        />

        <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-md bg-white/10 px-2 py-0.5 font-mono text-xs font-bold text-slate-200">
                All-Time #{driver.alltime_rank}
              </span>
              {driver.championships > 0 && (
                <span className="inline-flex items-center gap-1 rounded-full border border-amber-400/40 bg-amber-500/15 px-2.5 py-0.5 text-xs font-bold text-amber-300">
                  <Award className="h-3.5 w-3.5" /> {driver.championships}x Campeão Mundial
                </span>
              )}
              <span className="text-xs text-slate-400 font-mono">
                {driver.first_year}–{driver.last_year} · Auge {driver.peak_years}
              </span>
            </div>

            <h1 className="mt-2 text-3xl font-black tracking-tight text-white sm:text-4xl">
              {driver.name}
            </h1>
            <p className="mt-1 text-sm text-slate-400">
              {current_rating ? current_rating.team_name : driver.primary_team_name} ·{' '}
              {driver.nationality}
            </p>

            <div className="mt-4 flex flex-wrap gap-3 text-xs">
              <div className="rounded-xl border border-white/10 bg-black/35 px-3 py-2">
                <div className="text-slate-500">Largadas</div>
                <div className="font-mono text-base font-bold text-white">{driver.career_starts}</div>
              </div>
              <div className="rounded-xl border border-white/10 bg-black/35 px-3 py-2">
                <div className="text-slate-500">Vitórias</div>
                <div className="font-mono text-base font-bold text-white">{driver.career_wins}</div>
              </div>
              <div className="rounded-xl border border-white/10 bg-black/35 px-3 py-2">
                <div className="text-slate-500">Pódios</div>
                <div className="font-mono text-base font-bold text-white">{driver.career_podiums}</div>
              </div>
              <div className="rounded-xl border border-white/10 bg-black/35 px-3 py-2">
                <div className="text-slate-500">Auge 3 Anos</div>
                <div className="font-mono text-base font-bold text-amber-300">
                  {driver.peak_overall.toFixed(1)}
                </div>
              </div>
              <Link
                to={`/compare?a=${driver.reference}`}
                className="inline-flex items-center gap-1.5 rounded-xl bg-[#E10600] px-4 py-2 font-bold text-white hover:bg-red-600 transition-colors"
              >
                <GitCompareArrows className="h-4 w-4" /> Comparar Piloto
              </Link>
            </div>
          </div>

          <div className="flex flex-col items-end gap-3">
            {current_rating && (
              <div className="inline-flex rounded-xl border border-white/10 bg-black/40 p-1">
                <button
                  type="button"
                  onClick={() => setViewScope('current')}
                  className={`rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                    viewScope === 'current' ? 'bg-[#E10600] text-white' : 'text-slate-400 hover:text-white'
                  }`}
                >
                  Forma Atual ({current_rating.year})
                </button>
                <button
                  type="button"
                  onClick={() => setViewScope('alltime')}
                  className={`rounded-lg px-3 py-1.5 text-xs font-bold transition ${
                    viewScope === 'alltime' ? 'bg-[#E10600] text-white' : 'text-slate-400 hover:text-white'
                  }`}
                >
                  Histórico Carreira
                </button>
              </div>
            )}
            <div className="flex items-center gap-4">
              <div className="text-right">
                <div className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  {viewScope === 'current' ? 'Overall Atual' : 'Overall Histórico'}
                </div>
                <div className="font-mono text-xs text-slate-500">
                  exato {active.overall_raw.toFixed(2)}
                </div>
              </div>
              <OverallBadge score={active.overall} size="xl" showTier />
            </div>
          </div>
        </div>
      </section>

      {/* Radar + 5 Pillar Bars + Hygiene Audit */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <section className="rounded-2xl border border-white/10 bg-[#111520] p-5">
          <h2 className="text-sm font-bold uppercase tracking-wider text-slate-300">
            Radar dos 5 Pilares
          </h2>
          <p className="text-xs text-slate-500">Comparado à média base do grid (82)</p>
          <PillarRadar
            primary={{
              name: driver.name,
              color: teamColor || '#E10600',
              pace: active.pace_ovr,
              qualifying: active.quali_ovr,
              consistency: active.consistency_ovr,
              racecraft: active.racecraft_ovr,
              experience: active.experience_ovr,
            }}
            height={280}
          />
        </section>

        <section className="rounded-2xl border border-white/10 bg-[#111520] p-5 flex flex-col justify-between">
          <div>
            <h2 className="text-sm font-bold uppercase tracking-wider text-slate-300">
              Detalhamento Ponderado
            </h2>
            <p className="mb-4 text-xs text-slate-500">
              Notas convertidas de Z-scores padronizados após Bayesian Shrinkage
            </p>
            <PillarBars
              pace={active.pace_ovr}
              qualifying={active.quali_ovr}
              consistency={active.consistency_ovr}
              racecraft={active.racecraft_ovr}
              experience={active.experience_ovr}
            />
          </div>
        </section>

        <section className="rounded-2xl border border-white/10 bg-[#111520] p-5">
          <div className="flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-slate-300">
            <ShieldCheck className="h-4 w-4 text-emerald-400" />
            <h2>Higiene de Dados (Auditoria)</h2>
          </div>
          <p className="mt-1 text-xs text-slate-500">
            Separação rigorosa entre falhas mecânicas/equipe e erros próprios do piloto.
          </p>

          <div className="mt-4 space-y-2.5 text-xs">
            <div className="flex items-center justify-between rounded-xl bg-emerald-500/10 border border-emerald-500/20 px-3 py-2.5">
              <span className="inline-flex items-center gap-2 text-emerald-300 font-medium">
                <CheckCircle2 className="h-4 w-4" /> Corridas Concluídas Limpas
              </span>
              <span className="font-mono font-bold text-white">{hygiene_summary.clean_finishes}</span>
            </div>

            <div className="flex items-center justify-between rounded-xl bg-sky-500/10 border border-sky-500/20 px-3 py-2.5">
              <span className="inline-flex items-center gap-2 text-sky-300 font-medium">
                <Wrench className="h-4 w-4" /> DNFs Mecânicos Excluídos (0 penalidade)
              </span>
              <span className="font-mono font-bold text-white">
                {hygiene_summary.mechanical_dnfs_excluded}
              </span>
            </div>

            <div className="flex items-center justify-between rounded-xl bg-rose-500/10 border border-rose-500/20 px-3 py-2.5">
              <span className="inline-flex items-center gap-2 text-rose-300 font-medium">
                <TriangleAlert className="h-4 w-4" /> Abandonos por Erro / Colisão
              </span>
              <span className="font-mono font-bold text-white">
                {hygiene_summary.driver_error_dnfs}
              </span>
            </div>

            <div className="grid grid-cols-2 gap-2 pt-1">
              <div className="rounded-xl bg-black/35 border border-white/5 p-3">
                <div className="text-[11px] text-slate-400">Punições FIA (pista)</div>
                <div className="font-mono text-lg font-bold text-white">
                  {hygiene_summary.fia_penalties_count}
                </div>
              </div>
              <div className="rounded-xl bg-black/35 border border-white/5 p-3">
                <div className="text-[11px] text-slate-400">Voltas em Ar Limpo</div>
                <div className="font-mono text-lg font-bold text-white">
                  {hygiene_summary.clean_air_laps_total.toLocaleString('pt-BR')}
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>

      {/* Career Progression: Driver Overall vs Car Rating */}
      {progressionData.length > 0 && (
        <section className="rounded-2xl border border-white/10 bg-[#111520] p-6">
          <div className="mb-4">
            <h2 className="text-base font-bold text-white">
              Evolução na Carreira: Habilidade do Piloto vs. Performance do Carro
            </h2>
            <p className="text-xs text-slate-400">
              Quando a linha do piloto fica acima da linha do carro, o piloto superou o equipamento entregue pela equipe.
            </p>
          </div>
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={progressionData}>
                <CartesianGrid stroke="#1e2538" strokeDasharray="3 3" />
                <XAxis dataKey="year" stroke="#64748b" tick={{ fontSize: 11 }} />
                <YAxis domain={[60, 99]} stroke="#64748b" tick={{ fontSize: 11 }} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0e1320',
                    borderColor: 'rgba(255,255,255,0.12)',
                    borderRadius: '0.75rem',
                    fontSize: '12px',
                  }}
                />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="piloto"
                  name="Overall do Piloto"
                  stroke="#E10600"
                  strokeWidth={3}
                  dot={{ r: 3.5 }}
                />
                <Line
                  type="monotone"
                  dataKey="carro"
                  name="Performance do Carro"
                  stroke="#38BDF8"
                  strokeWidth={2}
                  strokeDasharray="5 4"
                  dot={{ r: 2.5 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}

      {/* Teammates Table */}
      <section className="rounded-2xl border border-white/10 bg-[#111520] overflow-hidden">
        <div className="border-b border-white/10 px-5 py-4">
          <h2 className="text-base font-bold text-white">
            Duelos Internos contra Companheiros de Equipe ({teammates.length})
          </h2>
          <p className="text-xs text-slate-400">
            Valores positivos (+) em Δ% indicam vantagem para {driver.name} sobre o companheiro.
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-white/10 bg-black/30 text-[11px] uppercase tracking-wider text-slate-400">
              <tr>
                <th className="px-4 py-3">Companheiro</th>
                <th className="px-3 py-3">Equipes & Anos</th>
                <th className="px-3 py-3">OVR Comp.</th>
                <th className="px-3 py-3">GPs Juntos</th>
                <th className="px-3 py-3">Δ% Classif.</th>
                <th className="px-3 py-3">Δ% Ritmo</th>
                <th className="px-3 py-3">H2H Classif.</th>
                <th className="px-3 py-3">H2H Corrida</th>
                <th className="px-3 py-3 text-right">Comparar</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {teammates.map((tm) => (
                <tr key={tm.teammate_id} className="hover:bg-white/[0.03]">
                  <td className="px-4 py-3 font-bold text-white">
                    <Link to={`/drivers/${tm.teammate_ref}`} className="hover:text-red-400">
                      {tm.teammate_name}
                    </Link>
                  </td>
                  <td className="px-3 py-3 text-slate-300">
                    <div>{tm.teams.join(', ')}</div>
                    <div className="font-mono text-[10px] text-slate-500">
                      {tm.seasons[0]}{tm.seasons.length > 1 ? `–${tm.seasons[tm.seasons.length - 1]}` : ''}
                    </div>
                  </td>
                  <td className="px-3 py-3">
                    <OverallBadge score={tm.teammate_overall} size="sm" />
                  </td>
                  <td className="px-3 py-3 font-mono text-slate-300">{tm.shared_races}</td>
                  <td className="px-3 py-3 font-mono font-bold">
                    {tm.quali_delta_pct !== null ? (
                      <span className={tm.quali_delta_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
                        {tm.quali_delta_pct >= 0 ? '+' : ''}
                        {tm.quali_delta_pct.toFixed(2)}%
                      </span>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td className="px-3 py-3 font-mono font-bold">
                    {tm.pace_delta_pct !== null ? (
                      <span className={tm.pace_delta_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}>
                        {tm.pace_delta_pct >= 0 ? '+' : ''}
                        {tm.pace_delta_pct.toFixed(2)}%
                      </span>
                    ) : (
                      '—'
                    )}
                  </td>
                  <td className="px-3 py-3 font-mono text-slate-200">
                    {tm.quali_wins}–{tm.quali_losses}
                  </td>
                  <td className="px-3 py-3 font-mono text-slate-200">
                    {tm.race_wins}–{tm.race_losses}
                  </td>
                  <td className="px-3 py-3 text-right">
                    <Link
                      to={`/compare?a=${driver.reference}&b=${tm.teammate_ref}`}
                      className="rounded-md bg-white/10 px-2.5 py-1 text-[11px] font-semibold text-white hover:bg-[#E10600]"
                    >
                      H2H
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Recent Race Metrics Log */}
      {recent_races.length > 0 && (
        <section className="rounded-2xl border border-white/10 bg-[#111520] overflow-hidden">
          <div className="border-b border-white/10 px-5 py-4">
            <h2 className="text-base font-bold text-white">Últimos GPs Analisados</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-white/10 bg-black/30 text-[11px] uppercase tracking-wider text-slate-400">
                <tr>
                  <th className="px-4 py-2.5">GP</th>
                  <th className="px-3 py-2.5">Equipe</th>
                  <th className="px-3 py-2.5">Grid → Chegada</th>
                  <th className="px-3 py-2.5">Status Higiene</th>
                  <th className="px-3 py-2.5">Sessão Quali</th>
                  <th className="px-3 py-2.5">Ar Limpo</th>
                  <th className="px-3 py-2.5">Δ Ritmo Comp.</th>
                  <th className="px-3 py-2.5">Ultrapassagens</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {recent_races.map((r) => (
                  <tr key={r.round_id} className="hover:bg-white/[0.02]">
                    <td className="px-4 py-2.5 font-medium text-white">
                      <span className="font-mono text-slate-400 mr-1.5">{r.year}</span>
                      {r.round_name}
                    </td>
                    <td className="px-3 py-2.5 text-slate-300">{r.team_name}</td>
                    <td className="px-3 py-2.5 font-mono text-slate-200">
                      P{r.grid ?? '?'} → {r.finish_pos ? `P${r.finish_pos}` : 'DNF'}
                    </td>
                    <td className="px-3 py-2.5">
                      <span
                        className={`rounded px-2 py-0.5 text-[10px] font-bold ${
                          r.status_category === 'CLEAN_FINISH'
                            ? 'bg-emerald-500/15 text-emerald-300'
                            : r.status_category === 'MECHANICAL_DNF'
                            ? 'bg-sky-500/15 text-sky-300'
                            : 'bg-rose-500/15 text-rose-300'
                        }`}
                      >
                        {r.status_category === 'CLEAN_FINISH'
                          ? 'Limpa'
                          : r.status_category === 'MECHANICAL_DNF'
                          ? 'Mecânico (Ignorado)'
                          : r.status_category === 'DRIVER_ERROR'
                          ? 'Erro Piloto'
                          : 'DNS'}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 font-mono text-slate-300">
                      {r.quali_session_used ?? '—'}
                      {r.quali_teammate_delta_pct !== null && (
                        <span
                          className={`ml-1.5 ${
                            r.quali_teammate_delta_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'
                          }`}
                        >
                          ({r.quali_teammate_delta_pct >= 0 ? '+' : ''}
                          {r.quali_teammate_delta_pct.toFixed(2)}%)
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-2.5 font-mono text-slate-300">
                      {r.clean_air_laps}/{r.clean_laps_total}
                    </td>
                    <td className="px-3 py-2.5 font-mono">
                      {r.pace_teammate_delta_pct !== null ? (
                        <span
                          className={
                            r.pace_teammate_delta_pct >= 0 ? 'text-emerald-400' : 'text-rose-400'
                          }
                        >
                          {r.pace_teammate_delta_pct >= 0 ? '+' : ''}
                          {r.pace_teammate_delta_pct.toFixed(2)}%
                        </span>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td className="px-3 py-2.5 font-mono text-slate-300">
                      +{r.on_track_overtakes} / -{r.on_track_overtaken}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
