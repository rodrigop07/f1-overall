import { Link, NavLink } from 'react-router-dom';
import { Activity, GitCompareArrows, Network, Sliders, Trophy, Users } from 'lucide-react';

const NAV_ITEMS = [
  { to: '/', label: 'Grid & Temporadas', icon: Users },
  { to: '/all-time', label: 'Histórico 1950–2026', icon: Trophy },
  { to: '/compare', label: 'Comparador H2H', icon: GitCompareArrows },
  { to: '/network', label: 'Rede de Companheiros', icon: Network },
  { to: '/sandbox', label: 'Sandbox & Metodologia', icon: Sliders },
];

export function Navbar() {
  return (
    <header className="sticky top-0 z-40 border-b border-white/10 bg-[#090B10]/90 backdrop-blur-md">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3 sm:px-6">
        <Link to="/" className="flex items-center gap-2.5">
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
            <p className="text-[11px] text-slate-400 hidden sm:block">
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
                `inline-flex items-center gap-1.5 whitespace-nowrap rounded-lg px-3 py-2 text-xs font-semibold transition-all ${
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
      </div>
    </header>
  );
}
