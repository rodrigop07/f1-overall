import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Award, Search, Trophy } from 'lucide-react';
import { api } from '../api/client';
import { OverallBadge } from '../components/OverallBadge';
import type { AllTimeDriverRating } from '../types/f1';

const DECADES = [
  { label: 'Todas', value: null },
  { label: '2020s', value: 2020 },
  { label: '2010s', value: 2010 },
  { label: '2000s', value: 2000 },
  { label: '1990s', value: 1990 },
  { label: '1980s', value: 1980 },
  { label: '1970s', value: 1970 },
  { label: '1960s', value: 1960 },
  { label: '1950s', value: 1950 },
];

export function AllTimeRankingsPage() {
  const [drivers, setDrivers] = useState<AllTimeDriverRating[]>([]);
  const [nationalities, setNationalities] = useState<string[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  const [search, setSearch] = useState('');
  const [decade, setDecade] = useState<number | null>(null);
  const [minStarts, setMinStarts] = useState<number>(10);
  const [nationality, setNationality] = useState<string>('');
  const [championsOnly, setChampionsOnly] = useState(false);
  const [sortBy, setSortBy] = useState('overall_raw');
  const [offset, setOffset] = useState(0);
  const limit = 50;

  useEffect(() => {
    setOffset(0);
  }, [search, decade, minStarts, nationality, championsOnly, sortBy]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    const timer = setTimeout(() => {
      api
        .getAllTimeRankings({
          decade,
          min_starts: minStarts,
          nationality: nationality || undefined,
          champions_only: championsOnly,
          search: search.trim() || undefined,
          sort_by: sortBy,
          limit,
          offset,
        })
        .then((res) => {
          if (!cancelled) {
            setDrivers(res.drivers);
            setTotal(res.total);
            if (res.nationalities.length > 0 && nationalities.length === 0) {
              setNationalities(res.nationalities);
            }
          }
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, 120);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [decade, minStarts, nationality, championsOnly, search, sortBy, offset]);

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-white/10 bg-gradient-to-br from-[#141927] via-[#0e121c] to-[#090B10] p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-amber-400/40 bg-amber-500/10 px-3 py-1 text-[11px] font-bold uppercase tracking-wider text-amber-300">
              <Trophy className="h-3.5 w-3.5" /> Ranking Histórico Universal (1950–2026)
            </div>
            <h1 className="mt-2.5 text-2xl font-black tracking-tight text-white sm:text-3xl">
              Todos os Pilotos da Fórmula 1
            </h1>
            <p className="mt-1 text-sm text-slate-400">
              Calibração conectada entre eras combinando <strong>75% Janela de Auge (3 anos)</strong> +{' '}
              <strong>25% Longevidade</strong>, com Bayesian Shrinkage para amostras pequenas.
            </p>
          </div>
          <div className="rounded-xl border border-white/10 bg-black/40 px-4 py-2.5 text-right">
            <div className="text-[11px] uppercase tracking-wider text-slate-400">Pilotos Encontrados</div>
            <div className="font-mono text-2xl font-black text-white tabular-nums">{total}</div>
          </div>
        </div>

        {/* Filters */}
        <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-5">
          <div className="relative lg:col-span-2">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-500" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Buscar piloto ou equipe (ex: Senna, Verstappen, Ferrari...)"
              className="w-full rounded-xl border border-white/10 bg-[#090B10] py-2 pl-9 pr-3 text-sm text-white placeholder:text-slate-500 focus:border-[#E10600] focus:outline-none"
            />
          </div>

          <select
            value={minStarts}
            onChange={(e) => setMinStarts(Number(e.target.value))}
            aria-label="Mínimo de GPs"
            className="rounded-xl border border-white/10 bg-[#090B10] px-3 py-2 text-xs font-semibold text-slate-200"
          >
            <option value={0}>Todos os pilotos (1+ GPs)</option>
            <option value={10}>Mínimo 10 GPs largados</option>
            <option value={30}>Mínimo 30 GPs largados</option>
            <option value={100}>Mínimo 100 GPs largados</option>
          </select>

          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            aria-label="Critério de ordenação"
            className="rounded-xl border border-white/10 bg-[#090B10] px-3 py-2 text-xs font-semibold text-slate-200"
          >
            <option value="overall_raw">Overall Histórico (Auge + Long.)</option>
            <option value="peak_overall">Auge Puro (Melhor Triênio)</option>
            <option value="longevity_overall">Longevidade de Carreira</option>
            <option value="pace_ovr">Ritmo de Corrida (35%)</option>
            <option value="quali_ovr">Classificação (25%)</option>
            <option value="consistency_ovr">Consistência (20%)</option>
            <option value="racecraft_ovr">Combate / Racecraft (15%)</option>
            <option value="experience_ovr">Experiência (5%)</option>
            <option value="career_wins">Vitórias na F1</option>
          </select>

          <div className="flex items-center gap-2">
            <select
              value={nationality}
              onChange={(e) => setNationality(e.target.value)}
              aria-label="Nacionalidade"
              className="w-full rounded-xl border border-white/10 bg-[#090B10] px-3 py-2 text-xs font-semibold text-slate-200"
            >
              <option value="">Todas as nacionalidades</option>
              {nationalities.map((nat) => (
                <option key={nat} value={nat}>
                  {nat}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-white/5 pt-4">
          <div className="flex flex-wrap gap-1.5">
            {DECADES.map((d) => (
              <button
                key={String(d.value)}
                type="button"
                onClick={() => setDecade(d.value)}
                className={`rounded-lg px-2.5 py-1 text-xs font-bold transition ${
                  decade === d.value
                    ? 'bg-[#E10600] text-white'
                    : 'bg-white/5 text-slate-300 hover:bg-white/10'
                }`}
              >
                {d.label}
              </button>
            ))}
          </div>

          <label className="inline-flex cursor-pointer items-center gap-2 text-xs font-semibold text-slate-300">
            <input
              type="checkbox"
              checked={championsOnly}
              onChange={(e) => setChampionsOnly(e.target.checked)}
              className="h-4 w-4 accent-[#E10600]"
            />
            Apenas Campeões Mundiais
          </label>
        </div>
      </section>

      {/* Results Table */}
      <section className="rounded-2xl border border-white/10 bg-[#111520] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-white/10 bg-black/35 text-[11px] uppercase tracking-wider text-slate-400">
              <tr>
                <th className="px-4 py-3">#</th>
                <th className="px-4 py-3">Piloto</th>
                <th className="px-3 py-3">Era / Auge</th>
                <th className="px-3 py-3">Overall</th>
                <th className="px-3 py-3">Auge 3A</th>
                <th className="px-3 py-3">RIT</th>
                <th className="px-3 py-3">CLA</th>
                <th className="px-3 py-3">CON</th>
                <th className="px-3 py-3">CMB</th>
                <th className="px-3 py-3">EXP</th>
                <th className="px-3 py-3 text-right">Vitórias / GPs</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {loading ? (
                <tr>
                  <td colSpan={11} className="px-4 py-12 text-center text-slate-400">
                    Carregando base histórica...
                  </td>
                </tr>
              ) : drivers.length === 0 ? (
                <tr>
                  <td colSpan={11} className="px-4 py-12 text-center text-slate-400">
                    Nenhum piloto encontrado com estes filtros.
                  </td>
                </tr>
              ) : (
                drivers.map((d) => (
                  <tr key={d.driver_id} className="hover:bg-white/[0.03] transition-colors">
                    <td className="px-4 py-3 font-mono font-bold text-slate-400 tabular-nums">
                      {d.rank}
                    </td>
                    <td className="px-4 py-3">
                      <Link to={`/drivers/${d.reference}`} className="flex items-center gap-2.5 group">
                        <span
                          className="h-6 w-1 rounded-full shrink-0"
                          style={{ backgroundColor: d.primary_team_color || '#94A3B8' }}
                        />
                        <div>
                          <div className="flex items-center gap-1.5 font-bold text-white group-hover:text-red-400 transition-colors">
                            {d.name}
                            {d.championships > 0 && (
                              <span className="inline-flex items-center gap-0.5 rounded bg-amber-500/15 px-1.5 py-0.5 font-mono text-[10px] text-amber-300 border border-amber-400/25">
                                <Award className="h-2.5 w-2.5" /> {d.championships}
                              </span>
                            )}
                          </div>
                          <div className="text-[11px] text-slate-400">
                            {d.primary_team_name} · {d.nationality}
                          </div>
                        </div>
                      </Link>
                    </td>
                    <td className="px-3 py-3 font-mono text-[11px] text-slate-300 tabular-nums">
                      <div>{d.first_year}–{d.last_year}</div>
                      <div className="text-[10px] text-slate-500">auge {d.peak_years}</div>
                    </td>
                    <td className="px-3 py-3">
                      <OverallBadge score={d.overall} size="sm" />
                    </td>
                    <td className="px-3 py-3 font-mono font-bold text-amber-300 tabular-nums">
                      {d.peak_overall.toFixed(1)}
                    </td>
                    <td className="px-3 py-3 font-mono text-slate-200 tabular-nums">{d.pace_ovr.toFixed(1)}</td>
                    <td className="px-3 py-3 font-mono text-slate-200 tabular-nums">{d.quali_ovr.toFixed(1)}</td>
                    <td className="px-3 py-3 font-mono text-slate-200 tabular-nums">{d.consistency_ovr.toFixed(1)}</td>
                    <td className="px-3 py-3 font-mono text-slate-200 tabular-nums">{d.racecraft_ovr.toFixed(1)}</td>
                    <td className="px-3 py-3 font-mono text-slate-400 tabular-nums">{d.experience_ovr.toFixed(1)}</td>
                    <td className="px-3 py-3 font-mono text-right text-slate-300 tabular-nums">
                      {d.career_wins} / {d.career_starts}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {total > limit && (
          <div className="flex items-center justify-between border-t border-white/10 px-5 py-3 text-xs text-slate-400">
            <span>
              Mostrando {offset + 1}–{Math.min(offset + limit, total)} de {total}
            </span>
            <div className="flex gap-2">
              <button
                type="button"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - limit))}
                className="rounded-lg border border-white/10 px-3 py-1.5 font-semibold text-white disabled:opacity-30 hover:bg-white/5"
              >
                Anterior
              </button>
              <button
                type="button"
                disabled={offset + limit >= total}
                onClick={() => setOffset(offset + limit)}
                className="rounded-lg border border-white/10 px-3 py-1.5 font-semibold text-white disabled:opacity-30 hover:bg-white/5"
              >
                Próxima
              </button>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
