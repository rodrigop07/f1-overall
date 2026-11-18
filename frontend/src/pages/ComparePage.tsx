import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ArrowRight, CloudRain, Compass, Flame, Gauge, GitCompareArrows, Link2 } from 'lucide-react';
import { api } from '../api/client';
import { CountryFlag } from '../components/CountryFlag';
import { DriverAvatar } from '../components/DriverAvatar';
import { ExportCardButton } from '../components/ExportCardButton';
import { OverallBadge } from '../components/OverallBadge';
import { PillarRadar } from '../components/PillarRadar';
import type { CompareResponse, DriverSummary } from '../types/f1';

const PRESETS = [
  { label: 'Senna vs Prost', a: 'senna', b: 'prost' },
  { label: 'Verstappen vs Hamilton', a: 'max_verstappen', b: 'hamilton' },
  { label: 'Senna vs Verstappen', a: 'senna', b: 'max_verstappen' },
  { label: 'Schumacher vs Alonso', a: 'michael_schumacher', b: 'alonso' },
  { label: 'Clark vs Fangio', a: 'clark', b: 'fangio' },
  { label: 'Leclerc vs Norris', a: 'leclerc', b: 'norris' },
];

export function ComparePage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [allDrivers, setAllDrivers] = useState<DriverSummary[]>([]);
  const [driverA, setDriverA] = useState(searchParams.get('a') || 'senna');
  const [driverB, setDriverB] = useState(searchParams.get('b') || 'max_verstappen');
  const [mode, setMode] = useState<'alltime' | 'current'>('alltime');
  const [searchA, setSearchA] = useState('');
  const [searchB, setSearchB] = useState('');
  const [data, setData] = useState<CompareResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getDriversList().then((res) => setAllDrivers(res.drivers)).catch(() => {});
  }, []);

  useEffect(() => {
    if (!driverA || !driverB) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    api
      .compareDrivers(driverA, driverB, mode)
      .then((res) => {
        if (!cancelled) setData(res);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Erro ao comparar');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [driverA, driverB, mode]);

  const selectPair = (a: string, b: string) => {
    setDriverA(a);
    setDriverB(b);
    setSearchParams({ a, b });
  };

  const optionsA = useMemo(() => {
    const q = searchA.trim().toLowerCase();
    const list = q
      ? allDrivers.filter((d) => d.name.toLowerCase().includes(q) || d.reference.includes(q))
      : allDrivers;
    return list.slice(0, 60);
  }, [allDrivers, searchA]);

  const optionsB = useMemo(() => {
    const q = searchB.trim().toLowerCase();
    const list = q
      ? allDrivers.filter((d) => d.name.toLowerCase().includes(q) || d.reference.includes(q))
      : allDrivers;
    return list.slice(0, 60);
  }, [allDrivers, searchB]);

  const ratingA = data?.driver_a.active_rating ?? data?.driver_a;
  const ratingB = data?.driver_b.active_rating ?? data?.driver_b;

  const pillarCompare = data && ratingA && ratingB
    ? [
        { label: 'Ritmo de Corrida (35%)', a: ratingA.pace_ovr, b: ratingB.pace_ovr },
        { label: 'Classificação (25%)', a: ratingA.quali_ovr, b: ratingB.quali_ovr },
        { label: 'Consistência (20%)', a: ratingA.consistency_ovr, b: ratingB.consistency_ovr },
        { label: 'Combate / Racecraft (15%)', a: ratingA.racecraft_ovr, b: ratingB.racecraft_ovr },
        { label: 'Experiência (5%)', a: ratingA.experience_ovr, b: ratingB.experience_ovr },
      ]
    : [];

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-white/10 bg-gradient-to-br from-[#141927] via-[#0e121c] to-[#090B10] p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-[#E10600]/40 bg-[#E10600]/10 px-3 py-1 text-[11px] font-bold uppercase tracking-wider text-red-300">
              <GitCompareArrows className="h-3.5 w-3.5" /> Comparador Universal Entre Eras
            </div>
            <h1 className="mt-2 text-2xl font-black tracking-tight text-white sm:text-3xl">
              Head-to-Head & Ponte de Calibração
            </h1>
            <p className="mt-1 text-sm text-slate-400">
              Compare quaisquer dois pilotos de 1950 a 2026 nos 5 pilares e visualize a cadeia exata de companheiros que conecta suas carreiras.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="inline-flex rounded-xl border border-white/10 bg-black/40 p-1">
              <button
                type="button"
                onClick={() => setMode('alltime')}
                className={`rounded-lg px-3.5 py-2 text-xs font-bold transition ${
                  mode === 'alltime' ? 'bg-[#E10600] text-white' : 'text-slate-300 hover:text-white'
                }`}
              >
                Histórico Carreira
              </button>
              <button
                type="button"
                onClick={() => setMode('current')}
                className={`rounded-lg px-3.5 py-2 text-xs font-bold transition ${
                  mode === 'current' ? 'bg-[#E10600] text-white' : 'text-slate-300 hover:text-white'
                }`}
              >
                Forma Atual (Se Ativo)
              </button>
            </div>
            {data && ratingA && ratingB && (
              <ExportCardButton
                label="Exportar Duelo PNG"
                data={{
                  mode: 'compare',
                  subtitle:
                    mode === 'current'
                      ? 'Comparação em Forma Atual'
                      : 'Comparação Histórica Carreira (1950–2026)',
                  driverA: {
                    name: data.driver_a.name,
                    teamName:
                      'team_name' in ratingA ? ratingA.team_name : ratingA.primary_team_name,
                    teamColor: '#E10600',
                    overall: ratingA.overall,
                    pace: ratingA.pace_ovr,
                    qualifying: ratingA.quali_ovr,
                    consistency: ratingA.consistency_ovr,
                    racecraft: ratingA.racecraft_ovr,
                    experience: ratingA.experience_ovr,
                  },
                  driverB: {
                    name: data.driver_b.name,
                    teamName:
                      'team_name' in ratingB ? ratingB.team_name : ratingB.primary_team_name,
                    teamColor: '#38BDF8',
                    overall: ratingB.overall,
                    pace: ratingB.pace_ovr,
                    qualifying: ratingB.quali_ovr,
                    consistency: ratingB.consistency_ovr,
                    racecraft: ratingB.racecraft_ovr,
                    experience: ratingB.experience_ovr,
                  },
                }}
              />
            )}
          </div>
        </div>

        {/* Selectors */}
        <div className="mt-5 grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="rounded-xl border border-white/10 bg-black/35 p-3.5 space-y-2">
            <label className="text-[11px] font-bold uppercase tracking-wider text-red-400">
              Piloto A
            </label>
            <input
              type="text"
              value={searchA}
              onChange={(e) => setSearchA(e.target.value)}
              placeholder="Filtrar nome..."
              className="w-full rounded-lg border border-white/10 bg-[#090B10] px-3 py-1.5 text-xs text-white placeholder:text-slate-500"
            />
            <select
              value={driverA}
              onChange={(e) => selectPair(e.target.value, driverB)}
              className="w-full rounded-lg border border-white/15 bg-[#121622] px-3 py-2 text-sm font-bold text-white"
            >
              {optionsA.map((d) => (
                <option key={d.driver_id} value={d.reference}>
                  {d.name} ({d.first_year}–{d.last_year}) · OVR {d.overall}
                </option>
              ))}
            </select>
          </div>

          <div className="rounded-xl border border-white/10 bg-black/35 p-3.5 space-y-2">
            <label className="text-[11px] font-bold uppercase tracking-wider text-sky-400">
              Piloto B
            </label>
            <input
              type="text"
              value={searchB}
              onChange={(e) => setSearchB(e.target.value)}
              placeholder="Filtrar nome..."
              className="w-full rounded-lg border border-white/10 bg-[#090B10] px-3 py-1.5 text-xs text-white placeholder:text-slate-500"
            />
            <select
              value={driverB}
              onChange={(e) => selectPair(driverA, e.target.value)}
              className="w-full rounded-lg border border-white/15 bg-[#121622] px-3 py-2 text-sm font-bold text-white"
            >
              {optionsB.map((d) => (
                <option key={d.driver_id} value={d.reference}>
                  {d.name} ({d.first_year}–{d.last_year}) · OVR {d.overall}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Presets */}
        <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-white/5 pt-4">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            Duelos Clássicos:
          </span>
          {PRESETS.map((p) => (
            <button
              key={p.label}
              type="button"
              onClick={() => selectPair(p.a, p.b)}
              className="rounded-lg bg-white/5 px-3 py-1 text-xs font-semibold text-slate-200 hover:bg-[#E10600] hover:text-white transition"
            >
              {p.label}
            </button>
          ))}
        </div>
      </section>

      {error && (
        <div className="rounded-xl border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-200">
          {error}
        </div>
      )}

      {loading && <div className="h-80 animate-pulse rounded-2xl bg-white/5" />}

      {!loading && data && ratingA && ratingB && (
        <>
          {/* Hero Side by Side + Radar */}
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
            {/* Side A */}
            <div className="rounded-2xl border border-white/10 bg-[#111520] p-5 flex flex-col justify-between">
              <div className="flex items-start gap-3">
                <DriverAvatar
                  reference={data.driver_a.reference}
                  name={data.driver_a.name}
                  abbreviation={data.driver_a.abbreviation}
                  teamColor={'team_color' in ratingA ? ratingA.team_color : data.driver_a.primary_team_color}
                  size="lg"
                />
                <div className="min-w-0">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-red-400">
                    Piloto A
                  </span>
                  <Link
                    to={`/drivers/${data.driver_a.reference}`}
                    className="mt-0.5 flex items-center gap-2 text-2xl font-black text-white hover:text-red-400"
                  >
                    <CountryFlag
                      countryCode={data.driver_a.country_code}
                      nationality={data.driver_a.nationality}
                      size="sm"
                    />
                    <span className="truncate">{data.driver_a.name}</span>
                  </Link>
                  <p className="text-xs text-slate-400">
                    {'team_name' in ratingA ? ratingA.team_name : ratingA.primary_team_name} · {data.driver_a.first_year}–{data.driver_a.last_year}
                  </p>
                </div>
              </div>
              <div className="my-5 flex items-center justify-between">
                <div className="space-y-1 text-xs text-slate-400">
                  <div>Títulos: <strong className="font-mono text-white">{data.driver_a.championships}</strong></div>
                  <div>Vitórias: <strong className="font-mono text-white">{data.driver_a.career_wins}</strong></div>
                  <div>GPs: <strong className="font-mono text-white">{data.driver_a.career_starts}</strong></div>
                  <div>Auge 3A: <strong className="font-mono text-amber-300">{data.driver_a.peak_overall.toFixed(1)}</strong></div>
                </div>
                <OverallBadge score={ratingA.overall} size="xl" showTier />
              </div>
              <div className="text-[11px] font-mono text-slate-400">
                Overall exato: {ratingA.overall_raw.toFixed(2)} ± {(ratingA.overall_ci ?? data.driver_a.overall_ci).toFixed(1)}
              </div>
            </div>

            {/* Dual Radar */}
            <div className="rounded-2xl border border-white/10 bg-[#111520] p-4 flex flex-col items-center justify-center">
              <PillarRadar
                primary={{
                  name: data.driver_a.name,
                  color: '#E10600',
                  pace: ratingA.pace_ovr,
                  qualifying: ratingA.quali_ovr,
                  consistency: ratingA.consistency_ovr,
                  racecraft: ratingA.racecraft_ovr,
                  experience: ratingA.experience_ovr,
                }}
                secondary={{
                  name: data.driver_b.name,
                  color: '#38BDF8',
                  pace: ratingB.pace_ovr,
                  qualifying: ratingB.quali_ovr,
                  consistency: ratingB.consistency_ovr,
                  racecraft: ratingB.racecraft_ovr,
                  experience: ratingB.experience_ovr,
                }}
                height={300}
              />
            </div>

            {/* Side B */}
            <div className="rounded-2xl border border-white/10 bg-[#111520] p-5 flex flex-col justify-between">
              <div className="flex items-start gap-3">
                <DriverAvatar
                  reference={data.driver_b.reference}
                  name={data.driver_b.name}
                  abbreviation={data.driver_b.abbreviation}
                  teamColor={'team_color' in ratingB ? ratingB.team_color : data.driver_b.primary_team_color}
                  size="lg"
                />
                <div className="min-w-0">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-sky-400">
                    Piloto B
                  </span>
                  <Link
                    to={`/drivers/${data.driver_b.reference}`}
                    className="mt-0.5 flex items-center gap-2 text-2xl font-black text-white hover:text-sky-400"
                  >
                    <CountryFlag
                      countryCode={data.driver_b.country_code}
                      nationality={data.driver_b.nationality}
                      size="sm"
                    />
                    <span className="truncate">{data.driver_b.name}</span>
                  </Link>
                  <p className="text-xs text-slate-400">
                    {'team_name' in ratingB ? ratingB.team_name : ratingB.primary_team_name} · {data.driver_b.first_year}–{data.driver_b.last_year}
                  </p>
                </div>
              </div>
              <div className="my-5 flex items-center justify-between">
                <div className="space-y-1 text-xs text-slate-400">
                  <div>Títulos: <strong className="font-mono text-white">{data.driver_b.championships}</strong></div>
                  <div>Vitórias: <strong className="font-mono text-white">{data.driver_b.career_wins}</strong></div>
                  <div>GPs: <strong className="font-mono text-white">{data.driver_b.career_starts}</strong></div>
                  <div>Auge 3A: <strong className="font-mono text-amber-300">{data.driver_b.peak_overall.toFixed(1)}</strong></div>
                </div>
                <OverallBadge score={ratingB.overall} size="xl" showTier />
              </div>
              <div className="text-[11px] font-mono text-slate-400">
                Overall exato: {ratingB.overall_raw.toFixed(2)} ± {(ratingB.overall_ci ?? data.driver_b.overall_ci).toFixed(1)}
              </div>
            </div>
          </div>

          {/* Pillar-by-pillar Bars */}
          <section className="rounded-2xl border border-white/10 bg-[#111520] p-6">
            <h2 className="mb-4 text-base font-bold text-white">Comparação Pilar por Pilar</h2>
            <div className="space-y-4">
              {pillarCompare.map((p) => {
                const diff = p.a - p.b;
                const aWins = diff > 0.05;
                const bWins = diff < -0.05;
                return (
                  <div key={p.label} className="space-y-1.5">
                    <div className="flex items-center justify-between text-xs">
                      <span className={`font-mono font-bold ${aWins ? 'text-red-400' : 'text-slate-300'}`}>
                        {p.a.toFixed(1)}
                      </span>
                      <span className="font-semibold text-slate-300">
                        {p.label}{' '}
                        <span className="font-mono text-[11px] text-slate-500">
                          ({diff >= 0 ? `+${diff.toFixed(1)}` : diff.toFixed(1)})
                        </span>
                      </span>
                      <span className={`font-mono font-bold ${bWins ? 'text-sky-400' : 'text-slate-300'}`}>
                        {p.b.toFixed(1)}
                      </span>
                    </div>
                    <div className="grid grid-cols-2 gap-2">
                      <div className="flex justify-end rounded-l-full bg-slate-800/80 h-2.5 overflow-hidden">
                        <div
                          className="h-full bg-[#E10600] rounded-l-full"
                          style={{ width: `${Math.max(4, Math.min(100, ((p.a - 60) / 39) * 100))}%` }}
                        />
                      </div>
                      <div className="rounded-r-full bg-slate-800/80 h-2.5 overflow-hidden">
                        <div
                          className="h-full bg-sky-400 rounded-r-full"
                          style={{ width: `${Math.max(4, Math.min(100, ((p.b - 60) / 39) * 100))}%` }}
                        />
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>

          {/* Specialties H2H */}
          <section className="rounded-2xl border border-white/10 bg-[#111520] p-6">
            <h2 className="mb-4 text-base font-bold text-white">Especialidades Contextuais</h2>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {[
                {
                  label: 'Chuva',
                  a: ratingA.wet_ovr ?? data.driver_a.wet_ovr,
                  b: ratingB.wet_ovr ?? data.driver_b.wet_ovr,
                  icon: CloudRain,
                },
                {
                  label: 'Circuitos de Rua',
                  a: ratingA.street_ovr ?? data.driver_a.street_ovr,
                  b: ratingB.street_ovr ?? data.driver_b.street_ovr,
                  icon: Compass,
                },
                {
                  label: 'Alta Velocidade',
                  a: ratingA.high_speed_ovr ?? data.driver_a.high_speed_ovr,
                  b: ratingB.high_speed_ovr ?? data.driver_b.high_speed_ovr,
                  icon: Gauge,
                },
                {
                  label: 'Gestão de Pneus',
                  a: ratingA.tyre_mgmt_ovr ?? data.driver_a.tyre_mgmt_ovr,
                  b: ratingB.tyre_mgmt_ovr ?? data.driver_b.tyre_mgmt_ovr,
                  icon: Flame,
                },
              ].map(({ label, a, b, icon: Icon }) => (
                <div key={label} className="rounded-xl border border-white/10 bg-black/35 p-3.5 text-xs">
                  <div className="flex items-center gap-1.5 font-semibold text-slate-300">
                    <Icon className="h-3.5 w-3.5 text-slate-400" />
                    {label}
                  </div>
                  <div className="mt-2.5 flex items-center justify-between font-mono text-base font-black">
                    <span className={a >= b ? 'text-red-400' : 'text-slate-400'}>{a.toFixed(1)}</span>
                    <span className="text-[11px] font-normal text-slate-600">vs</span>
                    <span className={b >= a ? 'text-sky-400' : 'text-slate-400'}>{b.toFixed(1)}</span>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* Direct Teammates H2H (if applicable) */}
          {data.direct_teammates && (
            <section className="rounded-2xl border border-emerald-500/30 bg-emerald-500/5 p-6">
              <h2 className="text-base font-bold text-emerald-300">
                Confronto Direto na Mesma Equipe ({data.direct_teammates.teams.join(', ')})
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                Temporadas juntos: {data.direct_teammates.seasons.join(', ')} · {data.direct_teammates.shared_races} GPs
              </p>
              <div className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4 text-xs">
                <div className="rounded-xl bg-black/40 p-3 border border-white/10">
                  <div className="text-slate-400">H2H Classificação</div>
                  <div className="font-mono text-lg font-bold text-white mt-0.5">
                    {data.direct_teammates.quali_wins_a} – {data.direct_teammates.quali_wins_b}
                  </div>
                </div>
                <div className="rounded-xl bg-black/40 p-3 border border-white/10">
                  <div className="text-slate-400">Δ% Mediano Quali (A vs B)</div>
                  <div className="font-mono text-lg font-bold text-white mt-0.5">
                    {data.direct_teammates.quali_delta_a_vs_b_pct !== null
                      ? `${data.direct_teammates.quali_delta_a_vs_b_pct >= 0 ? '+' : ''}${data.direct_teammates.quali_delta_a_vs_b_pct.toFixed(2)}%`
                      : '—'}
                  </div>
                </div>
                <div className="rounded-xl bg-black/40 p-3 border border-white/10">
                  <div className="text-slate-400">H2H Corrida</div>
                  <div className="font-mono text-lg font-bold text-white mt-0.5">
                    {data.direct_teammates.race_wins_a} – {data.direct_teammates.race_wins_b}
                  </div>
                </div>
                <div className="rounded-xl bg-black/40 p-3 border border-white/10">
                  <div className="text-slate-400">Δ% Mediano Ritmo (A vs B)</div>
                  <div className="font-mono text-lg font-bold text-white mt-0.5">
                    {data.direct_teammates.pace_delta_a_vs_b_pct !== null
                      ? `${data.direct_teammates.pace_delta_a_vs_b_pct >= 0 ? '+' : ''}${data.direct_teammates.pace_delta_a_vs_b_pct.toFixed(2)}%`
                      : '—'}
                  </div>
                </div>
              </div>
            </section>
          )}

          {/* Network Calibration Path */}
          <section className="rounded-2xl border border-white/10 bg-[#111520] p-6">
            <div className="flex items-center gap-2 text-white font-bold">
              <Link2 className="h-4 w-4 text-[#E10600]" />
              <h2>Ponte de Calibração na Rede de Companheiros ({data.calibration_path.length} elos)</h2>
            </div>
            <p className="mt-1 text-xs text-slate-400">
              Caminho matemático mais curto que conecta {data.driver_a.name} a {data.driver_b.name} através de duelos reais no mesmo carro.
            </p>

            {data.calibration_path.length === 0 ? (
              <p className="mt-4 text-xs text-slate-500">
                Não foi encontrada ponte conectada entre estes dois pilotos.
              </p>
            ) : (
              <div className="mt-4 flex flex-wrap items-center gap-2.5">
                {data.calibration_path.map((hop, idx) => (
                  <div key={`${hop.from.driver_id}-${hop.to.driver_id}`} className="flex items-center gap-2.5">
                    {idx === 0 && (
                      <Link
                        to={`/drivers/${hop.from.reference}`}
                        className="rounded-xl border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs font-bold text-white hover:bg-red-500/20"
                      >
                        {hop.from.name}
                      </Link>
                    )}
                    <div className="flex flex-col items-center rounded-lg border border-white/10 bg-black/40 px-2.5 py-1.5 text-[10px]">
                      <div className="flex items-center gap-1 font-semibold text-slate-300">
                        <ArrowRight className="h-3 w-3 text-[#E10600]" />
                        {hop.teams[0]} ({hop.seasons[0]}
                        {hop.seasons.length > 1 ? `–${hop.seasons[hop.seasons.length - 1]}` : ''})
                      </div>
                      <div className="font-mono text-slate-400">
                        {hop.shared_races} GPs
                        {hop.quali_delta_pct !== null
                          ? ` · Q ${hop.quali_delta_pct >= 0 ? '+' : ''}${hop.quali_delta_pct.toFixed(2)}%`
                          : ''}
                      </div>
                    </div>
                    <Link
                      to={`/drivers/${hop.to.reference}`}
                      className={`rounded-xl border px-3 py-2 text-xs font-bold text-white ${
                        idx === data.calibration_path.length - 1
                          ? 'border-sky-500/40 bg-sky-500/10 hover:bg-sky-500/20'
                          : 'border-white/15 bg-white/5 hover:bg-white/10'
                      }`}
                    >
                      {hop.to.name}
                    </Link>
                  </div>
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
