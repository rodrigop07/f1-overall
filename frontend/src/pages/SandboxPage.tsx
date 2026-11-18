import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Activity, RotateCcw, Scale, Sliders, Zap } from 'lucide-react';
import {
  Bar,
  BarChart,
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
import type { DiagnosticsResponse, SimulateResponse } from '../types/f1';

const DEFAULT_WEIGHTS = {
  pace: 35,
  qualifying: 25,
  consistency: 20,
  racecraft: 15,
  experience: 5,
};

export function SandboxPage() {
  const [scope, setScope] = useState<'current' | 'season' | 'alltime'>('current');
  const [year, setYear] = useState<number>(2026);
  const [weightsPct, setWeightsPct] = useState(DEFAULT_WEIGHTS);
  const [shrinkageM, setShrinkageM] = useState(10);
  const [halfLife, setHalfLife] = useState(16);
  const [baseOvr, setBaseOvr] = useState(82);
  const [scaleFactor, setScaleFactor] = useState(6);

  const [simData, setSimData] = useState<SimulateResponse | null>(null);
  const [diag, setDiag] = useState<DiagnosticsResponse | null>(null);

  useEffect(() => {
    api.getDiagnostics().then(setDiag).catch(() => {});
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      const sum =
        weightsPct.pace +
        weightsPct.qualifying +
        weightsPct.consistency +
        weightsPct.racecraft +
        weightsPct.experience || 1;
      api
        .simulate({
          scope,
          year: scope === 'season' ? year : null,
          weights: {
            pace: weightsPct.pace / sum,
            qualifying: weightsPct.qualifying / sum,
            consistency: weightsPct.consistency / sum,
            racecraft: weightsPct.racecraft / sum,
            experience: weightsPct.experience / sum,
          },
          shrinkage_m: shrinkageM,
          half_life_races: halfLife,
          base_ovr: baseOvr,
          scale_factor: scaleFactor,
          min_starts: scope === 'alltime' ? 10 : 0,
          limit: 30,
        })
        .then(setSimData)
        .catch(() => {});
    }, 60);
    return () => clearTimeout(timer);
  }, [scope, year, weightsPct, shrinkageM, halfLife, baseOvr, scaleFactor]);

  const totalPct =
    weightsPct.pace +
    weightsPct.qualifying +
    weightsPct.consistency +
    weightsPct.racecraft +
    weightsPct.experience;

  const normalizeWeights = () => {
    if (totalPct <= 0) return;
    setWeightsPct({
      pace: Math.round((weightsPct.pace / totalPct) * 100),
      qualifying: Math.round((weightsPct.qualifying / totalPct) * 100),
      consistency: Math.round((weightsPct.consistency / totalPct) * 100),
      racecraft: Math.round((weightsPct.racecraft / totalPct) * 100),
      experience: Math.round((weightsPct.experience / totalPct) * 100),
    });
  };

  const resetDefaults = () => {
    setWeightsPct(DEFAULT_WEIGHTS);
    setShrinkageM(10);
    setHalfLife(scope === 'current' ? 16 : 14);
    setBaseOvr(82);
    setScaleFactor(6);
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <section className="rounded-2xl border border-white/10 bg-gradient-to-br from-[#141927] via-[#0e121c] to-[#090B10] p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-emerald-400/40 bg-emerald-500/10 px-3 py-1 text-[11px] font-bold uppercase tracking-wider text-emerald-300">
              <Sliders className="h-3.5 w-3.5" /> Simulação Estatística em Tempo Real
            </div>
            <h1 className="mt-2 text-2xl font-black tracking-tight text-white sm:text-3xl">
              Sandbox de Metodologia & Auditoria do Modelo
            </h1>
            <p className="mt-1 text-sm text-slate-400">
              Ajuste pesos dos 5 pilares, fator de Bayesian Shrinkage (m), decaimento exponencial (H) e escala 0–99 para observar o impacto imediato no ranking.
            </p>
          </div>
          {simData && (
            <div className="inline-flex items-center gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-xs font-mono font-bold text-emerald-300">
              <Zap className="h-4 w-4" /> Recalculado em {simData.elapsed_ms.toFixed(1)} ms
            </div>
          )}
        </div>
      </section>

      {/* Interactive Simulator */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <aside className="lg:col-span-4 rounded-2xl border border-white/10 bg-[#111520] p-5 space-y-5 h-fit">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold uppercase tracking-wider text-white">
              Parâmetros do Pipeline
            </h2>
            <button
              type="button"
              onClick={resetDefaults}
              className="inline-flex items-center gap-1 rounded-lg bg-white/5 px-2.5 py-1 text-[11px] font-semibold text-slate-300 hover:bg-white/10"
            >
              <RotateCcw className="h-3 w-3" /> Padrão
            </button>
          </div>

          <div className="grid grid-cols-3 gap-1.5 rounded-xl bg-black/40 p-1">
            {(['current', 'season', 'alltime'] as const).map((sc) => (
              <button
                key={sc}
                type="button"
                onClick={() => setScope(sc)}
                className={`rounded-lg py-1.5 text-xs font-bold transition ${
                  scope === sc ? 'bg-[#E10600] text-white' : 'text-slate-400 hover:text-white'
                }`}
              >
                {sc === 'current' ? 'Atual' : sc === 'season' ? 'Temporada' : 'All-Time'}
              </button>
            ))}
          </div>

          {scope === 'season' && (
            <div>
              <label className="text-xs font-semibold text-slate-400">Ano da Temporada</label>
              <input
                type="number"
                min={1950}
                max={2026}
                value={year}
                onChange={(e) => setYear(Number(e.target.value))}
                className="mt-1 w-full rounded-lg border border-white/10 bg-[#090B10] px-3 py-1.5 font-mono text-sm text-white"
              />
            </div>
          )}

          {/* Pillar Weight Sliders */}
          <div className="space-y-3 border-t border-white/10 pt-4">
            <div className="flex items-center justify-between text-xs">
              <span className="font-bold text-slate-200">Pesos dos 5 Pilares</span>
              <span
                className={`font-mono font-bold ${
                  totalPct === 100 ? 'text-emerald-400' : 'text-amber-300'
                }`}
              >
                Soma: {totalPct}%
              </span>
            </div>

            {(
              [
                ['pace', 'Ritmo de Corrida'],
                ['qualifying', 'Classificação'],
                ['consistency', 'Consistência / Consciência'],
                ['racecraft', 'Combate / Racecraft'],
                ['experience', 'Experiência'],
              ] as const
            ).map(([k, label]) => (
              <div key={k} className="space-y-1">
                <div className="flex justify-between text-xs">
                  <span className="text-slate-300">{label}</span>
                  <span className="font-mono font-bold text-white">{weightsPct[k]}%</span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={70}
                  value={weightsPct[k]}
                  onChange={(e) =>
                    setWeightsPct({ ...weightsPct, [k]: Number(e.target.value) })
                  }
                  className="w-full accent-[#E10600]"
                />
              </div>
            ))}

            {totalPct !== 100 && (
              <button
                type="button"
                onClick={normalizeWeights}
                className="w-full rounded-lg border border-amber-400/30 bg-amber-500/10 py-1.5 text-xs font-bold text-amber-300 hover:bg-amber-500/20"
              >
                Normalizar Soma para 100%
              </button>
            )}
          </div>

          {/* Mathematical Hyperparameters */}
          <div className="space-y-3 border-t border-white/10 pt-4">
            <div className="space-y-1">
              <div className="flex justify-between text-xs">
                <span className="text-slate-300">Bayesian Shrinkage (m GPs)</span>
                <span className="font-mono font-bold text-white">{shrinkageM}</span>
              </div>
              <input
                type="range"
                min={0}
                max={30}
                value={shrinkageM}
                onChange={(e) => setShrinkageM(Number(e.target.value))}
                className="w-full accent-sky-400"
              />
            </div>

            {scope !== 'alltime' && (
              <div className="space-y-1">
                <div className="flex justify-between text-xs">
                  <span className="text-slate-300">Meia-vida Exponencial (H GPs)</span>
                  <span className="font-mono font-bold text-white">{halfLife}</span>
                </div>
                <input
                  type="range"
                  min={4}
                  max={48}
                  value={halfLife}
                  onChange={(e) => setHalfLife(Number(e.target.value))}
                  className="w-full accent-emerald-400"
                />
              </div>
            )}

            <div className="grid grid-cols-2 gap-3 pt-1">
              <div className="space-y-1">
                <div className="flex justify-between text-[11px] text-slate-400">
                  <span>Média Base</span>
                  <span className="font-mono text-white">{baseOvr}</span>
                </div>
                <input
                  type="range"
                  min={76}
                  max={86}
                  value={baseOvr}
                  onChange={(e) => setBaseOvr(Number(e.target.value))}
                  className="w-full accent-purple-400"
                />
              </div>
              <div className="space-y-1">
                <div className="flex justify-between text-[11px] text-slate-400">
                  <span>Fator Z (σ)</span>
                  <span className="font-mono text-white">{scaleFactor}</span>
                </div>
                <input
                  type="range"
                  min={3}
                  max={9}
                  step={0.5}
                  value={scaleFactor}
                  onChange={(e) => setScaleFactor(Number(e.target.value))}
                  className="w-full accent-purple-400"
                />
              </div>
            </div>
          </div>
        </aside>

        {/* Simulated Table */}
        <section className="lg:col-span-8 rounded-2xl border border-white/10 bg-[#111520] overflow-hidden">
          <div className="border-b border-white/10 px-5 py-4 flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-white">Ranking Simulado (Comparado ao Padrão)</h2>
              <p className="text-xs text-slate-400">
                Top 30 pilotos recalculados dinamicamente com os seus hiperparâmetros
              </p>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-white/10 bg-black/30 text-[11px] uppercase tracking-wider text-slate-400">
                <tr>
                  <th className="px-4 py-3">#</th>
                  <th className="px-2 py-3">Δ Pos</th>
                  <th className="px-4 py-3">Piloto</th>
                  <th className="px-3 py-3">Simulado</th>
                  <th className="px-3 py-3">Padrão</th>
                  <th className="px-3 py-3">Δ OVR</th>
                  <th className="px-3 py-3">RIT</th>
                  <th className="px-3 py-3">CLA</th>
                  <th className="px-3 py-3">CON</th>
                  <th className="px-3 py-3">CMB</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {simData?.results.map((r) => (
                  <tr key={r.driver_id} className="hover:bg-white/[0.03]">
                    <td className="px-4 py-2.5 font-mono font-bold text-slate-300">{r.rank}</td>
                    <td className="px-2 py-2.5 font-mono font-bold">
                      {r.delta_rank > 0 ? (
                        <span className="text-emerald-400">▲{r.delta_rank}</span>
                      ) : r.delta_rank < 0 ? (
                        <span className="text-rose-400">▼{Math.abs(r.delta_rank)}</span>
                      ) : (
                        <span className="text-slate-600">—</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5">
                      <Link to={`/drivers/${r.reference}`} className="font-bold text-white hover:text-red-400">
                        {r.name}
                      </Link>
                      <div className="text-[10px] text-slate-500">{r.team_name}</div>
                    </td>
                    <td className="px-3 py-2.5">
                      <OverallBadge score={r.overall} size="sm" />
                    </td>
                    <td className="px-3 py-2.5 font-mono text-slate-400">
                      {r.baseline_overall.toFixed(1)}
                    </td>
                    <td className="px-3 py-2.5 font-mono font-bold">
                      <span
                        className={
                          r.delta_overall > 0.05
                            ? 'text-emerald-400'
                            : r.delta_overall < -0.05
                            ? 'text-rose-400'
                            : 'text-slate-500'
                        }
                      >
                        {r.delta_overall >= 0 ? '+' : ''}
                        {r.delta_overall.toFixed(2)}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 font-mono text-slate-300">{r.pace_ovr.toFixed(1)}</td>
                    <td className="px-3 py-2.5 font-mono text-slate-300">{r.quali_ovr.toFixed(1)}</td>
                    <td className="px-3 py-2.5 font-mono text-slate-300">{r.consistency_ovr.toFixed(1)}</td>
                    <td className="px-3 py-2.5 font-mono text-slate-300">{r.racecraft_ovr.toFixed(1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      {/* Empirical Model Diagnostics */}
      {diag && (
        <section className="space-y-6">
          <div className="flex items-center gap-2 text-lg font-black text-white">
            <Scale className="h-5 w-5 text-[#E10600]" />
            <h2>Diagnósticos Empíricos do Modelo (1950–2026)</h2>
          </div>

          {/* Variance Decomposition + Coverage KPIs */}
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
            <div className="rounded-2xl border border-white/10 bg-[#111520] p-6 space-y-4">
              <h3 className="text-sm font-bold uppercase tracking-wider text-slate-300">
                Isolamento Empírico: Carro vs. Piloto (Modelo LMM)
              </h3>
              <p className="text-xs text-slate-400">
                Fração da variância bruta explicada pela equipe/temporada versus habilidade individual estimada na rede.
              </p>

              {[
                ['Ritmo de Corrida (Ar Limpo)', diag.variance_decomposition.race_pace],
                ['Classificação (Última Sessão Igual)', diag.variance_decomposition.qualifying],
              ].map(([title, vd]) => {
                const stats = vd as DiagnosticsResponse['variance_decomposition']['race_pace'];
                return (
                  <div key={String(title)} className="space-y-2">
                    <div className="flex justify-between text-xs">
                      <span className="font-semibold text-white">{String(title)}</span>
                      <span className="font-mono text-slate-300">
                        Carro <strong className="text-sky-400">{stats.car_share_pct}%</strong> · Piloto{' '}
                        <strong className="text-[#E10600]">{stats.driver_share_pct}%</strong>
                      </span>
                    </div>
                    <div className="flex h-3 w-full overflow-hidden rounded-full bg-slate-800">
                      <div
                        className="bg-sky-500"
                        style={{ width: `${stats.car_share_pct}%` }}
                      />
                      <div
                        className="bg-[#E10600]"
                        style={{ width: `${stats.driver_share_pct}%` }}
                      />
                    </div>
                    <div className="text-[11px] font-mono text-slate-500">
                      R² global: {(stats.total_explained_r2 * 100).toFixed(1)}% ·{' '}
                      {stats.n_session_obs.toLocaleString('pt-BR')} sessões ·{' '}
                      {stats.n_pair_obs.toLocaleString('pt-BR')} duelos diretos
                    </div>
                  </div>
                );
              })}
            </div>

            <div className="rounded-2xl border border-white/10 bg-[#111520] p-6">
              <div className="flex items-center gap-2 text-sm font-bold uppercase tracking-wider text-slate-300">
                <Activity className="h-4 w-4 text-emerald-400" />
                <h3>Cobertura da Base Processada</h3>
              </div>
              <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
                <div className="rounded-xl bg-black/35 border border-white/5 p-3">
                  <div className="text-slate-400">Pilotos Avaliados</div>
                  <div className="font-mono text-2xl font-black text-white">
                    {diag.coverage_stats.total_drivers_rated}
                  </div>
                </div>
                <div className="rounded-xl bg-black/35 border border-white/5 p-3">
                  <div className="text-slate-400">GPs Analisados</div>
                  <div className="font-mono text-2xl font-black text-white">
                    {diag.coverage_stats.total_rounds_analyzed}
                  </div>
                </div>
                <div className="rounded-xl bg-black/35 border border-white/5 p-3">
                  <div className="text-slate-400">Voltas em Ar Limpo</div>
                  <div className="font-mono text-xl font-black text-emerald-400">
                    {diag.coverage_stats.total_clean_air_laps.toLocaleString('pt-BR')}
                  </div>
                </div>
                <div className="rounded-xl bg-black/35 border border-white/5 p-3">
                  <div className="text-slate-400">DNFs Mecânicos Filtrados</div>
                  <div className="font-mono text-xl font-black text-sky-400">
                    {diag.coverage_stats.total_mechanical_dnfs_excluded.toLocaleString('pt-BR')}
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Age Curve & Lap 1 Grid Curve */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="rounded-2xl border border-white/10 bg-[#111520] p-6">
              <h3 className="text-sm font-bold text-white">
                Curva de Idade Estimada no LMM (18–45 anos)
              </h3>
              <p className="mb-4 text-xs text-slate-400">
                Efeito médio de maturação e declínio físico em ritmo e classificação (âncora = 27 anos).
              </p>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={diag.age_curve}>
                    <CartesianGrid stroke="#1e2538" strokeDasharray="3 3" />
                    <XAxis dataKey="age" stroke="#64748b" tick={{ fontSize: 11 }} />
                    <YAxis stroke="#64748b" tick={{ fontSize: 11 }} unit="%" />
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
                      dataKey="pace_delta_pct"
                      name="Ritmo Corrida (%)"
                      stroke="#E10600"
                      strokeWidth={2.5}
                      dot={false}
                    />
                    <Line
                      type="monotone"
                      dataKey="quali_delta_pct"
                      name="Classificação (%)"
                      stroke="#38BDF8"
                      strokeWidth={2.5}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="rounded-2xl border border-white/10 bg-[#111520] p-6">
              <h3 className="text-sm font-bold text-white">
                Expectativa Empírica de Posições na Volta 1 por Slot do Grid
              </h3>
              <p className="mb-4 text-xs text-slate-400">
                Base usada para neutralizar o viés natural de largar na frente (menos espaço para ganhar) vs. fundo do pelotão.
              </p>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={diag.lap1_grid_curve}>
                    <CartesianGrid stroke="#1e2538" strokeDasharray="3 3" />
                    <XAxis dataKey="grid" stroke="#64748b" tick={{ fontSize: 11 }} />
                    <YAxis stroke="#64748b" tick={{ fontSize: 11 }} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#0e1320',
                        borderColor: 'rgba(255,255,255,0.12)',
                        borderRadius: '0.75rem',
                        fontSize: '12px',
                      }}
                    />
                    <Bar
                      dataKey="expected_gain"
                      name="Saldo Médio Esperado (Volta 1)"
                      fill="#FBBF24"
                      radius={[4, 4, 0, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
