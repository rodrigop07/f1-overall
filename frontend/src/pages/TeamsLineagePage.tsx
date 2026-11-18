import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, Award, Car, Search, Shield, Trophy } from 'lucide-react';
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { api } from '../api/client';
import { CountryFlag } from '../components/CountryFlag';
import { DriverAvatar } from '../components/DriverAvatar';
import { OverallBadge } from '../components/OverallBadge';
import type { TeamLineageDetailResponse, TeamLineageSummary } from '../types/f1';

export function TeamsLineagePage() {
  const { slug } = useParams<{ slug?: string }>();
  const [lineages, setLineages] = useState<TeamLineageSummary[]>([]);
  const [detail, setDetail] = useState<TeamLineageDetailResponse | null>(null);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    if (slug) {
      api
        .getTeamLineageDetail(slug)
        .then((res) => {
          if (!cancelled) setDetail(res);
        })
        .catch((err) => {
          if (!cancelled) setError(err instanceof Error ? err.message : 'Equipe não encontrada');
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    } else {
      setDetail(null);
      api
        .getTeamLineages()
        .then((res) => {
          if (!cancelled) setLineages(res.lineages);
        })
        .catch((err) => {
          if (!cancelled) setError(err instanceof Error ? err.message : 'Erro ao carregar linhagens');
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }

    return () => {
      cancelled = true;
    };
  }, [slug]);

  const filteredLineages = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return lineages;
    return lineages.filter(
      (l) =>
        l.name.toLowerCase().includes(q) ||
        l.era_names.some((en) => en.toLowerCase().includes(q)) ||
        (l.top_driver_name && l.top_driver_name.toLowerCase().includes(q))
    );
  }, [lineages, search]);

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-white/10 bg-gradient-to-br from-[#141927] via-[#0e121c] to-[#090B10] p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            {slug ? (
              <Link
                to="/teams"
                className="inline-flex items-center gap-1.5 text-xs font-bold text-slate-400 hover:text-white mb-2"
              >
                <ArrowLeft className="h-3.5 w-3.5" /> Todas as Franquias
              </Link>
            ) : (
              <div className="inline-flex items-center gap-2 rounded-full border border-[#E10600]/40 bg-[#E10600]/10 px-3 py-1 text-[11px] font-bold uppercase tracking-wider text-red-300">
                <Shield className="h-3.5 w-3.5" /> Linhagens Históricas de Construtores
              </div>
            )}

            <h1 className="mt-2 text-2xl font-black tracking-tight text-white sm:text-3xl">
              {slug && detail ? detail.name : 'Equipes & Franquias da F1 (1950–2026)'}
            </h1>
            <p className="mt-1 text-sm text-slate-400">
              {slug && detail
                ? `Evolução anual do Índice do Chassi isolado via modelo LMM e Hall da Fama histórico da franquia.`
                : 'Acompanhe as linhagens reais de fábricas (ex.: Tyrrell → Brawn → Mercedes, Stewart → Red Bull, Toleman → Alpine) e seus melhores pilotos.'}
            </p>
          </div>

          {!slug && (
            <div className="relative w-full lg:w-72">
              <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-500" />
              <input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Buscar equipe ou piloto..."
                className="w-full rounded-xl border border-white/10 bg-[#090B10] py-2 pl-9 pr-3 text-sm text-white placeholder:text-slate-500 focus:border-[#E10600] focus:outline-none"
              />
            </div>
          )}
        </div>
      </section>

      {loading && <div className="h-80 animate-pulse rounded-2xl bg-white/5" />}

      {error && (
        <div className="rounded-xl border border-red-500/40 bg-red-500/10 p-5 text-sm text-red-200">
          {error}
        </div>
      )}

      {/* Lineages Cards Grid */}
      {!loading && !slug && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredLineages.map((lin) => (
            <Link
              key={lin.slug}
              to={`/teams/${lin.slug}`}
              className="group relative overflow-hidden rounded-2xl border border-white/10 bg-[#111520] p-5 hover:border-white/25 hover:bg-[#151a28] transition-all"
            >
              <div
                className="absolute inset-x-0 top-0 h-1.5"
                style={{ backgroundColor: lin.primary_color || '#E10600' }}
              />
              <div className="flex items-start justify-between gap-3 pt-1">
                <div>
                  <h2 className="text-lg font-black text-white group-hover:text-red-400 transition-colors">
                    {lin.name}
                  </h2>
                  <div className="mt-1 font-mono text-xs text-slate-400">
                    {lin.first_year}–{lin.last_year} · {lin.seasons_count} temporadas
                  </div>
                </div>
                <OverallBadge score={Math.round(lin.peak_car_rating)} size="sm" />
              </div>

              <div className="mt-3 flex flex-wrap gap-1">
                {lin.era_names.map((en) => (
                  <span
                    key={en}
                    className="rounded bg-white/5 px-2 py-0.5 text-[10px] font-medium text-slate-300 border border-white/10"
                  >
                    {en}
                  </span>
                ))}
              </div>

              <div className="mt-4 grid grid-cols-3 gap-2 border-t border-white/5 pt-3 text-xs">
                <div>
                  <div className="text-[10px] text-slate-500">Vitórias</div>
                  <div className="font-mono font-bold text-white flex items-center gap-1">
                    <Trophy className="h-3 w-3 text-amber-400" /> {lin.race_wins}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] text-slate-500">Pico Chassi</div>
                  <div className="font-mono font-bold text-emerald-300">
                    {lin.peak_car_rating.toFixed(1)}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] text-slate-500">Ícone</div>
                  <div className="truncate font-bold text-slate-200">
                    {lin.top_driver_name ?? '—'}
                  </div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}

      {/* Detail View */}
      {!loading && slug && detail && (
        <>
          <div className="flex flex-wrap gap-2">
            {detail.era_names.map((en) => (
              <span
                key={en}
                className="rounded-xl border border-white/10 bg-[#111520] px-3 py-1 text-xs font-bold text-slate-200"
              >
                {en}
              </span>
            ))}
          </div>

          <section className="rounded-2xl border border-white/10 bg-[#111520] p-6">
            <div className="mb-4 flex items-center gap-2">
              <Car className="h-4 w-4 text-[#E10600]" />
              <h2 className="text-base font-bold text-white">
                Linha do Tempo de Força do Carro (Índice LMM 60–99)
              </h2>
            </div>
            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={detail.timeline}>
                  <defs>
                    <linearGradient id="carGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={detail.primary_color || '#E10600'} stopOpacity={0.45} />
                      <stop offset="95%" stopColor={detail.primary_color || '#E10600'} stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
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
                  <Area
                    type="monotone"
                    dataKey="car_rating"
                    name="Índice do Carro"
                    stroke={detail.primary_color || '#E10600'}
                    strokeWidth={3}
                    fill="url(#carGrad)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </section>

          <section className="rounded-2xl border border-white/10 bg-[#111520] overflow-hidden">
            <div className="border-b border-white/10 px-5 py-4 flex items-center gap-2">
              <Award className="h-4 w-4 text-amber-400" />
              <div>
                <h2 className="text-base font-bold text-white">Hall da Fama da Franquia</h2>
                <p className="text-xs text-slate-400">
                  Principais pilotos que correram pela linhagem ordenados por vitórias e auge no carro.
                </p>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-white/10 bg-black/30 text-[11px] uppercase tracking-wider text-slate-400">
                  <tr>
                    <th className="px-4 py-3">Piloto</th>
                    <th className="px-3 py-3">Período na Equipe</th>
                    <th className="px-3 py-3">Largadas</th>
                    <th className="px-3 py-3">Vitórias</th>
                    <th className="px-3 py-3">Pódios</th>
                    <th className="px-3 py-3">Auge na Equipe</th>
                    <th className="px-3 py-3 text-right">OVR Carreira</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {detail.hall_of_fame.map((d) => (
                    <tr key={d.driver_id} className="hover:bg-white/[0.03]">
                      <td className="px-4 py-3">
                        <Link to={`/drivers/${d.reference}`} className="flex items-center gap-2.5 group">
                          <DriverAvatar
                            reference={d.reference}
                            name={d.name}
                            teamColor={detail.primary_color}
                            size="xs"
                          />
                          <div className="flex items-center gap-1.5 font-bold text-white group-hover:text-red-400">
                            <CountryFlag countryCode={d.country_code} nationality={d.nationality} size="xs" />
                            <span>{d.name}</span>
                          </div>
                        </Link>
                      </td>
                      <td className="px-3 py-3 font-mono text-slate-300">
                        {d.first_year}–{d.last_year}
                      </td>
                      <td className="px-3 py-3 font-mono text-slate-200">{d.starts_for_team}</td>
                      <td className="px-3 py-3 font-mono font-bold text-amber-300">{d.wins_for_team}</td>
                      <td className="px-3 py-3 font-mono text-slate-200">{d.podiums_for_team}</td>
                      <td className="px-3 py-3 font-mono font-bold text-white">
                        {d.peak_stint_ovr !== null ? d.peak_stint_ovr.toFixed(1) : '—'}
                      </td>
                      <td className="px-3 py-3 text-right">
                        {d.alltime_overall !== null ? (
                          <OverallBadge score={d.alltime_overall} size="sm" />
                        ) : (
                          '—'
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
  );
}
