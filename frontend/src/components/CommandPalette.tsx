import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Calendar, Flag, Search, Shield, Sparkles, User, X } from 'lucide-react';
import { api } from '../api/client';
import type { DriverSummary, SeasonMeta, TeamLineageSummary } from '../types/f1';

interface CommandItem {
  id: string;
  kind: 'driver' | 'season' | 'team' | 'page';
  title: string;
  subtitle: string;
  badge?: string;
  to: string;
}

const STATIC_PAGES: CommandItem[] = [
  { id: 'page-grid', kind: 'page', title: 'Grid & Temporadas', subtitle: 'Power Ranking atual e temporadas 1950–2026', to: '/' },
  { id: 'page-alltime', kind: 'page', title: 'Histórico 1950–2026', subtitle: 'Ranking All-Time com pico, longevidade e especialidades', to: '/all-time' },
  { id: 'page-races', kind: 'page', title: 'Raio-X de GPs', subtitle: 'Análise detalhada volta a volta, stints de pneus e SC', to: '/races' },
  { id: 'page-teams', kind: 'page', title: 'Linhagens de Equipes', subtitle: 'Evolução de chassis e Hall da Fama das franquias', to: '/teams' },
  { id: 'page-whatif', kind: 'page', title: 'Simulador E se...?', subtitle: 'Mundial em carros iguais e Monte Carlo de troca de assento', to: '/what-if' },
  { id: 'page-compare', kind: 'page', title: 'Comparador H2H', subtitle: 'Duelo direto e caminho em grafo entre qualquer dupla', to: '/compare' },
  { id: 'page-network', kind: 'page', title: 'Rede de Companheiros', subtitle: 'Grafo global de calibração desde 1950', to: '/network' },
  { id: 'page-sandbox', kind: 'page', title: 'Sandbox & Metodologia', subtitle: 'Ajuste de pesos dos 5 pilares e decomposição de variância', to: '/sandbox' },
];

interface CommandPaletteProps {
  open: boolean;
  onClose: () => void;
}

export function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [query, setQuery] = useState('');
  const [activeIdx, setActiveIdx] = useState(0);
  const [drivers, setDrivers] = useState<DriverSummary[]>([]);
  const [seasons, setSeasons] = useState<SeasonMeta[]>([]);
  const [teams, setTeams] = useState<TeamLineageSummary[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!open) return;
    setTimeout(() => inputRef.current?.focus(), 20);
    if (loaded) return;
    Promise.all([
      api.getDriversList('').catch(() => ({ drivers: [] })),
      api.getSeasons().catch(() => ({ seasons: [] })),
      api.getTeamLineages().catch(() => ({ lineages: [] })),
    ]).then(([dRes, sRes, tRes]) => {
      setDrivers(dRes.drivers);
      setSeasons(sRes.seasons);
      setTeams(tRes.lineages);
      setLoaded(true);
    });
  }, [open, loaded]);

  const items = useMemo<CommandItem[]>(() => {
    const q = query.trim().toLowerCase();
    const results: CommandItem[] = [];

    if (!q) {
      results.push(...STATIC_PAGES.slice(0, 5));
      for (const d of drivers.slice(0, 6)) {
        results.push({
          id: `drv-${d.reference}`,
          kind: 'driver',
          title: d.name,
          subtitle: `${d.primary_team_name} (${d.first_year}–${d.last_year}) · ${d.career_starts} GPs`,
          badge: `OVR ${d.overall}`,
          to: `/drivers/${d.reference}`,
        });
      }
      return results;
    }

    for (const p of STATIC_PAGES) {
      if (p.title.toLowerCase().includes(q) || p.subtitle.toLowerCase().includes(q)) {
        results.push(p);
      }
    }

    for (const d of drivers) {
      if (
        d.name.toLowerCase().includes(q) ||
        d.reference.toLowerCase().includes(q) ||
        (d.abbreviation && d.abbreviation.toLowerCase().includes(q)) ||
        d.primary_team_name.toLowerCase().includes(q)
      ) {
        results.push({
          id: `drv-${d.reference}`,
          kind: 'driver',
          title: d.name,
          subtitle: `${d.primary_team_name} (${d.first_year}–${d.last_year}) · ${d.career_wins} vitórias`,
          badge: `OVR ${d.overall}`,
          to: `/drivers/${d.reference}`,
        });
      }
      if (results.length >= 24) break;
    }

    for (const t of teams) {
      if (
        t.name.toLowerCase().includes(q) ||
        t.era_names.some((en) => en.toLowerCase().includes(q))
      ) {
        results.push({
          id: `team-${t.slug}`,
          kind: 'team',
          title: t.name,
          subtitle: `${t.first_year}–${t.last_year} · ${t.race_wins} vitórias · Pico ${t.peak_car_rating}`,
          badge: 'Equipe',
          to: `/teams/${t.slug}`,
        });
      }
    }

    for (const s of seasons) {
      if (String(s.year).includes(q)) {
        results.push({
          id: `season-${s.year}`,
          kind: 'season',
          title: `Temporada ${s.year}`,
          subtitle: `${s.driver_count} pilotos · Líder: ${s.top_driver_name || 'N/A'}`,
          badge: `${s.year}`,
          to: `/?year=${s.year}`,
        });
        results.push({
          id: `races-${s.year}`,
          kind: 'season',
          title: `GPs da Temporada ${s.year}`,
          subtitle: `Explorar Raio-X corrida a corrida de ${s.year}`,
          badge: 'GPs',
          to: `/races?year=${s.year}`,
        });
      }
    }

    return results.slice(0, 18);
  }, [query, drivers, teams, seasons]);

  useEffect(() => {
    setActiveIdx(0);
  }, [query, open]);

  if (!open) return null;

  const goTo = (item: CommandItem) => {
    navigate(item.to);
    onClose();
    setQuery('');
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/75 pt-20 px-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full max-w-2xl overflow-hidden rounded-2xl border border-white/15 bg-[#111520] shadow-2xl"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => {
          if (e.key === 'Escape') onClose();
          if (e.key === 'ArrowDown') {
            e.preventDefault();
            setActiveIdx((i) => Math.min(items.length - 1, i + 1));
          }
          if (e.key === 'ArrowUp') {
            e.preventDefault();
            setActiveIdx((i) => Math.max(0, i - 1));
          }
          if (e.key === 'Enter' && items[activeIdx]) {
            e.preventDefault();
            goTo(items[activeIdx]);
          }
        }}
      >
        <div className="flex items-center gap-3 border-b border-white/10 px-4 py-3.5">
          <Search className="h-4 w-4 text-slate-400" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Buscar piloto (ex: Senna, Verstappen), temporada (2021), equipe ou página..."
            className="w-full bg-transparent text-sm text-white placeholder-slate-500 focus:outline-none"
          />
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1 text-slate-400 hover:bg-white/10 hover:text-white"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="max-h-96 overflow-y-auto p-2 space-y-1">
          {items.length === 0 ? (
            <div className="py-10 text-center text-sm text-slate-500">
              Nenhum resultado encontrado para &ldquo;{query}&rdquo;.
            </div>
          ) : (
            items.map((item, idx) => {
              const Icon =
                item.kind === 'driver'
                  ? User
                  : item.kind === 'team'
                    ? Shield
                    : item.kind === 'season'
                      ? Calendar
                      : item.title.includes('Raio-X')
                        ? Flag
                        : Sparkles;
              return (
                <button
                  key={item.id}
                  type="button"
                  onMouseEnter={() => setActiveIdx(idx)}
                  onClick={() => goTo(item)}
                  className={`flex w-full items-center justify-between gap-3 rounded-xl px-3 py-2.5 text-left transition-colors cursor-pointer ${
                    idx === activeIdx
                      ? 'bg-[#E10600]/20 text-white border border-red-500/30'
                      : 'text-slate-300 hover:bg-white/5 border border-transparent'
                  }`}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-white/5 text-slate-300">
                      <Icon className="h-4 w-4" />
                    </div>
                    <div className="min-w-0">
                      <div className="truncate text-sm font-bold text-white">{item.title}</div>
                      <div className="truncate text-xs text-slate-400">{item.subtitle}</div>
                    </div>
                  </div>
                  {item.badge && (
                    <span className="shrink-0 rounded-md bg-white/10 px-2 py-0.5 font-mono text-[11px] font-bold text-slate-200">
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })
          )}
        </div>

        <div className="flex items-center justify-between border-t border-white/10 bg-black/20 px-4 py-2 text-[11px] text-slate-500">
          <span>↑↓ navegar · Enter abrir · Esc fechar</span>
          <span>820+ pilotos · 77 temporadas</span>
        </div>
      </div>
    </div>
  );
}
