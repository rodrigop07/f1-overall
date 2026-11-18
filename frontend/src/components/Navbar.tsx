import { useState } from 'react';
import { Link, NavLink } from 'react-router-dom';
import {
  Activity,
  Flag,
  GitCompareArrows,
  Network,
  RefreshCw,
  Search,
  Shield,
  Sliders,
  Sparkles,
  Trophy,
  User,
  Users,
} from 'lucide-react';
import { api } from '../api/client';
import { AUTHOR_PROFILE } from '../constants/author';
import { GitHubIcon } from './GitHubIcon';

const NAV_ITEMS = [
  { to: '/', label: 'Grid', icon: Users },
  { to: '/all-time', label: 'Histórico', icon: Trophy },
  { to: '/races', label: 'Raio-X GPs', icon: Flag },
  { to: '/teams', label: 'Equipes', icon: Shield },
  { to: '/what-if', label: 'E se...?', icon: Sparkles },
  { to: '/compare', label: 'H2H', icon: GitCompareArrows },
  { to: '/network', label: 'Rede', icon: Network },
  { to: '/sandbox', label: 'Sandbox', icon: Sliders },
  { to: '/sobre', label: 'Sobre', icon: User },
];

interface NavbarProps {
  onOpenSearch?: () => void;
}

export function Navbar({ onOpenSearch }: NavbarProps) {
  const [syncing, setSyncing] = useState(false);
  const [syncNotice, setSyncNotice] = useState<string | null>(null);

  const handleSync = async () => {
    if (syncing) return;
    setSyncing(true);
    setSyncNotice(null);
    try {
      const res = await api.triggerSync();
      setSyncNotice(
        `Base ${res.year} atualizada (${res.coverage.total_rounds_analyzed} GPs).`
      );
      setTimeout(() => setSyncNotice(null), 5000);
    } catch {
      setSyncNotice('Falha ao sincronizar agora.');
      setTimeout(() => setSyncNotice(null), 4000);
    } finally {
      setSyncing(false);
    }
  };

  return (
    <header className="sticky top-0 z-40 border-b border-white/10 bg-[#090B10]/90 backdrop-blur-md">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
        <Link to="/" className="flex items-center gap-2.5 shrink-0">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[#E10600] text-white shadow-[0_0_18px_rgba(225,6,0,0.45)]">
            <Activity className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="text-base font-black tracking-tight text-white">F1 OVERALL</span>
              <span className="rounded bg-white/10 px-1.5 py-0.5 font-mono text-[10px] font-bold text-slate-300">
                1950–2026
              </span>
            </div>
            <p className="text-[11px] text-slate-400 hidden xl:block">
              Isolamento Estatístico Piloto vs. Carro (0–99)
            </p>
          </div>
        </Link>

        <nav className="flex items-center gap-1 overflow-x-auto py-1">
          {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `inline-flex items-center gap-1.5 whitespace-nowrap rounded-lg px-2.5 py-1.5 text-xs font-semibold transition-all ${
                  isActive
                    ? 'bg-[#E10600] text-white shadow-[0_0_16px_rgba(225,6,0,0.3)]'
                    : 'text-slate-300 hover:bg-white/5 hover:text-white'
                }`
              }
            >
              <Icon className="h-3.5 w-3.5" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="flex items-center gap-2 shrink-0">
          <a
            href={AUTHOR_PROFILE.githubUrl}
            target="_blank"
            rel="noopener noreferrer"
            title={`${AUTHOR_PROFILE.name} (@${AUTHOR_PROFILE.handle}) no GitHub`}
            className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-2.5 py-1.5 text-xs font-semibold text-slate-300 hover:bg-white/10 hover:text-white transition"
          >
            <GitHubIcon className="h-3.5 w-3.5" />
            <span className="hidden xl:inline">@{AUTHOR_PROFILE.handle}</span>
          </a>
          {onOpenSearch && (
            <button
              type="button"
              onClick={onOpenSearch}
              title="Busca Rápida (Ctrl+K)"
              className="inline-flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-2.5 py-1.5 text-xs font-medium text-slate-300 hover:bg-white/10 hover:text-white transition cursor-pointer"
            >
              <Search className="h-3.5 w-3.5 text-slate-400" />
              <span className="hidden sm:inline">Buscar</span>
              <kbd className="hidden md:inline rounded bg-black/40 px-1.5 py-0.5 font-mono text-[10px] text-slate-400 border border-white/10">
                Ctrl+K
              </kbd>
            </button>
          )}
          <button
            type="button"
            onClick={handleSync}
            disabled={syncing}
            title="Sincronizar últimos GPs e recomputar"
            className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/5 px-2.5 py-1.5 text-xs font-semibold text-slate-300 hover:bg-white/10 hover:text-white transition cursor-pointer disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${syncing ? 'animate-spin text-red-400' : 'text-emerald-400'}`} />
            <span className="hidden sm:inline">{syncing ? 'Sincronizando...' : 'Sincronizar'}</span>
          </button>
        </div>
      </div>
      {syncNotice && (
        <div className="border-t border-white/10 bg-emerald-500/10 px-4 py-1.5 text-center text-xs font-medium text-emerald-300">
          {syncNotice}
        </div>
      )}
    </header>
  );
}
