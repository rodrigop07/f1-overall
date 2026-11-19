import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, ExternalLink, FolderGit2 } from 'lucide-react';
import { AUTHOR_PROFILE } from '../constants/author';
import { CountryFlag } from './CountryFlag';
import { GitHubIcon } from './GitHubIcon';

const QUICK_LINKS = [
  { to: '/', label: 'Grid & Temporadas' },
  { to: '/all-time', label: 'Ranking Histórico' },
  { to: '/what-if', label: 'Simulador E se...?' },
  { to: '/sandbox', label: 'Sandbox & Metodologia' },
  { to: '/sobre', label: 'Sobre o Autor' },
];

export function Footer() {
  const [avatarError, setAvatarError] = useState(false);

  return (
    <footer className="border-t border-white/10 bg-[#07090E] text-slate-300">
      <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6">
        <div className="grid grid-cols-1 gap-8 md:grid-cols-12">
          {/* Coluna 1: Autor / Criador */}
          <div className="md:col-span-5 space-y-3">
            <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
              Criador &amp; Mantenedor
            </div>
            <div className="flex items-start gap-3.5">
              {!avatarError ? (
                <img
                  src={AUTHOR_PROFILE.avatarUrl}
                  alt={AUTHOR_PROFILE.name}
                  loading="lazy"
                  onError={() => setAvatarError(true)}
                  className="h-11 w-11 shrink-0 rounded-xl object-cover ring-1 ring-white/15"
                />
              ) : (
                <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[#E10600]/20 font-mono text-sm font-bold text-[#E10600] ring-1 ring-[#E10600]/30">
                  {AUTHOR_PROFILE.initials}
                </div>
              )}

              <div className="min-w-0 space-y-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-bold text-white">{AUTHOR_PROFILE.name}</span>
                  <span className="rounded-md border border-white/10 bg-white/5 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-slate-300">
                    @{AUTHOR_PROFILE.handle}
                  </span>
                  <CountryFlag countryCode={AUTHOR_PROFILE.countryCode} size="xs" />
                </div>
                <p className="text-xs text-slate-400">
                  {AUTHOR_PROFILE.institution} · {AUTHOR_PROFILE.location}
                </p>
                <Link
                  to="/sobre"
                  className="inline-flex items-center gap-1 pt-0.5 text-xs font-semibold text-[#ff4b45] hover:text-white transition"
                >
                  <span>Conhecer o autor &amp; arquitetura</span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </Link>
              </div>
            </div>
          </div>

          {/* Coluna 2: Navegação Rápida */}
          <div className="md:col-span-3 space-y-3">
            <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
              Navegação Rápida
            </div>
            <ul className="space-y-2">
              {QUICK_LINKS.map((item) => (
                <li key={item.to}>
                  <Link
                    to={item.to}
                    className="text-xs font-medium text-slate-400 hover:text-white transition"
                  >
                    {item.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Coluna 3: Código Aberto & Fontes */}
          <div className="md:col-span-4 space-y-3">
            <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
              Código Aberto &amp; Fontes
            </div>
            <div className="space-y-2">
              <a
                href={AUTHOR_PROFILE.githubUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-between gap-2 rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-xs font-semibold text-slate-200 hover:border-white/20 hover:bg-white/[0.07] transition"
              >
                <span className="flex items-center gap-2 truncate">
                  <GitHubIcon className="h-4 w-4 shrink-0 text-white" />
                  <span className="truncate">Perfil no GitHub (@{AUTHOR_PROFILE.handle})</span>
                </span>
                <ExternalLink className="h-3.5 w-3.5 shrink-0 text-slate-400" />
              </a>

              <a
                href={AUTHOR_PROFILE.repoUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center justify-between gap-2 rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-xs font-semibold text-slate-200 hover:border-white/20 hover:bg-white/[0.07] transition"
              >
                <span className="flex items-center gap-2 truncate">
                  <FolderGit2 className="h-4 w-4 shrink-0 text-[#E10600]" />
                  <span className="truncate">Repositório {AUTHOR_PROFILE.repoName}</span>
                </span>
                <ExternalLink className="h-3.5 w-3.5 shrink-0 text-slate-400" />
              </a>
            </div>
            <p className="text-[11px] leading-relaxed text-slate-500">
              Telemetria e resultados históricos via FastF1 &amp; Jolpica-F1 API (1950–2026).
            </p>
          </div>
        </div>

        {/* Faixa inferior */}
        <div className="mt-8 flex flex-col gap-2 border-t border-white/10 pt-5 text-[11px] text-slate-500 sm:flex-row sm:items-center sm:justify-between">
          <div>
            © 2026 {AUTHOR_PROFILE.name} (@{AUTHOR_PROFILE.handle}) · {AUTHOR_PROFILE.institutionShort} ·{' '}
            {AUTHOR_PROFILE.location}
          </div>
          <div>
            Projeto independente de engenharia e estatística aplicada à F1, sem vínculo comercial oficial com a Formula 1.
          </div>
        </div>
      </div>
    </footer>
  );
}
