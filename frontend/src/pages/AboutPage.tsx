import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowUpRight,
  Cpu,
  Database,
  ExternalLink,
  FolderGit2,
  GitBranch,
  GraduationCap,
  Layers,
  MapPin,
  Terminal,
} from 'lucide-react';
import { CountryFlag } from '../components/CountryFlag';
import { GitHubIcon } from '../components/GitHubIcon';
import { AUTHOR_PROFILE } from '../constants/author';

interface GitHubPublicStats {
  publicRepos: number;
  followers: number;
}

const EXPLORE_LINKS = [
  { to: '/', label: 'Grid Atual & Temporadas' },
  { to: '/all-time', label: 'Ranking Histórico' },
  { to: '/what-if', label: 'Simulador E se...?' },
  { to: '/compare', label: 'Comparador H2H' },
  { to: '/network', label: 'Rede de Companheiros' },
  { to: '/sandbox', label: 'Sandbox & Metodologia' },
];

export function AboutPage() {
  const [avatarError, setAvatarError] = useState(false);
  const [githubStats, setGithubStats] = useState<GitHubPublicStats>({
    publicRepos: AUTHOR_PROFILE.defaultPublicRepos,
    followers: AUTHOR_PROFILE.defaultFollowers,
  });

  useEffect(() => {
    const controller = new AbortController();

    fetch(AUTHOR_PROFILE.githubApiUrl, { signal: controller.signal })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!data || typeof data !== 'object') return;
        setGithubStats((prev) => ({
          publicRepos: typeof data.public_repos === 'number' ? data.public_repos : prev.publicRepos,
          followers: typeof data.followers === 'number' ? data.followers : prev.followers,
        }));
      })
      .catch(() => {
        // Fallback silencioso para os valores padrão públicos em AUTHOR_PROFILE.
      });

    return () => controller.abort();
  }, []);

  return (
    <div className="space-y-8">
      {/* Seção 1: Hero Card — Criador & Engenheiro Responsável */}
      <section className="rounded-2xl border border-white/10 bg-gradient-to-br from-[#E10600]/15 via-[#111520] to-[#0B0E16] p-6 sm:p-8">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-start">
            {!avatarError ? (
              <img
                src={AUTHOR_PROFILE.avatarUrl}
                alt={AUTHOR_PROFILE.name}
                onError={() => setAvatarError(true)}
                className="h-[88px] w-[88px] shrink-0 rounded-2xl object-cover ring-2 ring-[#E10600]/50 shadow-[0_0_28px_rgba(225,6,0,0.25)]"
              />
            ) : (
              <div className="flex h-[88px] w-[88px] shrink-0 items-center justify-center rounded-2xl bg-[#E10600]/20 font-mono text-2xl font-black text-[#E10600] ring-2 ring-[#E10600]/50 shadow-[0_0_28px_rgba(225,6,0,0.25)]">
                {AUTHOR_PROFILE.initials}
              </div>
            )}

            <div className="space-y-3">
              {/* Chips superiores */}
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full border border-[#E10600]/40 bg-[#E10600]/15 px-2.5 py-0.5 font-mono text-[10px] font-bold tracking-wider text-red-300">
                  CRIADOR &amp; MANTENEDOR
                </span>
                <span className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-2.5 py-0.5 text-[11px] font-medium text-slate-200">
                  <CountryFlag countryCode={AUTHOR_PROFILE.countryCode} size="xs" />
                  <span>{AUTHOR_PROFILE.location}</span>
                </span>
                <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-0.5 font-mono text-[11px] font-bold text-slate-200">
                  {AUTHOR_PROFILE.institutionShort}
                </span>
              </div>

              {/* Título & handle */}
              <div className="flex flex-wrap items-center gap-3">
                <h1 className="text-2xl font-black tracking-tight text-white sm:text-3xl">
                  {AUTHOR_PROFILE.name}
                </h1>
                <span className="rounded-lg border border-white/10 bg-black/30 px-2.5 py-1 font-mono text-xs font-bold text-slate-300">
                  @{AUTHOR_PROFILE.handle}
                </span>
              </div>

              {/* Instituição e Localização */}
              <div className="flex flex-wrap items-center gap-x-5 gap-y-1.5 text-sm text-slate-300">
                <span className="inline-flex items-center gap-1.5">
                  <GraduationCap className="h-4 w-4 text-[#E10600]" />
                  <span>{AUTHOR_PROFILE.institution}</span>
                </span>
                <span className="inline-flex items-center gap-1.5 text-slate-400">
                  <MapPin className="h-4 w-4 text-slate-400" />
                  <span>{AUTHOR_PROFILE.location}</span>
                </span>
              </div>

              {/* Bloco estilo terminal */}
              <div className="rounded-xl border border-white/10 bg-black/40 p-3.5 font-mono text-xs">
                <div className="mb-1.5 flex items-center gap-2 text-[11px] text-emerald-400">
                  <Terminal className="h-3.5 w-3.5" />
                  <span>{AUTHOR_PROFILE.handle}@github ~ $ ./maintainer.sh</span>
                </div>
                <p className="font-sans text-xs italic leading-relaxed text-slate-300">
                  &ldquo;{AUTHOR_PROFILE.tagline}&rdquo;
                </p>
              </div>
            </div>
          </div>

          {/* Botões de ação */}
          <div className="flex flex-col gap-2.5 sm:flex-row lg:flex-col lg:min-w-[240px]">
            <a
              href={AUTHOR_PROFILE.githubUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-[#E10600] px-4 py-2.5 text-xs font-bold text-white shadow-[0_0_20px_rgba(225,6,0,0.3)] hover:bg-[#ff1e17] transition"
            >
              <GitHubIcon className="h-4 w-4" />
              <span>Seguir @{AUTHOR_PROFILE.handle} no GitHub</span>
              <ExternalLink className="h-3.5 w-3.5" />
            </a>

            <a
              href={AUTHOR_PROFILE.repoUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center gap-2 rounded-xl border border-white/15 bg-white/5 px-4 py-2.5 text-xs font-semibold text-white hover:bg-white/10 transition"
            >
              <FolderGit2 className="h-4 w-4 text-slate-300" />
              <span>Ver Código-Fonte (f1-overall)</span>
              <ExternalLink className="h-3.5 w-3.5 text-slate-400" />
            </a>

            <a
              href={AUTHOR_PROFILE.issuesUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/5 px-4 py-2.5 text-xs font-semibold text-slate-200 hover:bg-white/10 transition"
            >
              <GitBranch className="h-4 w-4 text-slate-400" />
              <span>Abrir Issue / Contribuir</span>
              <ExternalLink className="h-3.5 w-3.5 text-slate-400" />
            </a>
          </div>
        </div>

        {/* Mini-métricas em 4 cards */}
        <div className="mt-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
          <div className="rounded-xl border border-white/10 bg-black/30 p-3.5">
            <div className="text-[11px] font-medium text-slate-400">Repositórios Públicos</div>
            <div className="mt-1 flex items-baseline gap-2">
              <span className="font-mono text-xl font-black text-white">
                {githubStats.publicRepos}
              </span>
              <span className="font-mono text-[11px] text-slate-400">
                · {githubStats.followers} seguidores
              </span>
            </div>
          </div>

          <div className="rounded-xl border border-white/10 bg-black/30 p-3.5">
            <div className="text-[11px] font-medium text-slate-400">Comunidade Open Source</div>
            <div className="mt-1 font-mono text-xl font-black text-white">
              No GitHub desde {AUTHOR_PROFILE.memberSince}
            </div>
          </div>

          <div className="rounded-xl border border-white/10 bg-black/30 p-3.5">
            <div className="text-[11px] font-medium text-slate-400">Instituição</div>
            <div className="mt-1 font-mono text-xl font-black text-white">
              {AUTHOR_PROFILE.institutionShort}
            </div>
            <div className="truncate text-[11px] text-slate-400">{AUTHOR_PROFILE.location}</div>
          </div>

          <div className="rounded-xl border border-white/10 bg-black/30 p-3.5">
            <div className="text-[11px] font-medium text-slate-400">Escopo do F1 Overall</div>
            <div className="mt-1 font-mono text-xl font-black text-white">1950–2026</div>
            <div className="text-[11px] text-slate-400">820+ pilotos avaliados</div>
          </div>
        </div>
      </section>

      {/* Seção 2: Grid 2 Colunas — Engenharia + Stack & Filosofia */}
      <section className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        {/* Coluna Esquerda: Engenharia do F1 Overall */}
        <div className="lg:col-span-7 rounded-2xl border border-white/10 bg-[#111520] p-6 space-y-5">
          <div>
            <h2 className="text-lg font-extrabold tracking-tight text-white">
              Engenharia do F1 Overall
            </h2>
            <p className="mt-1 text-xs text-slate-400">
              Arquitetura completa projetada para isolar o desempenho individual do piloto da performance do equipamento.
            </p>
          </div>

          <div className="space-y-3.5">
            <div className="flex items-start gap-3.5 rounded-xl border border-white/10 bg-white/[0.02] p-4">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[#E10600]/15 text-[#E10600]">
                <Cpu className="h-4 w-4" />
              </div>
              <div className="space-y-1">
                <h3 className="text-sm font-bold text-white">
                  Motor Matemático de Isolamento Piloto vs. Carro
                </h3>
                <p className="text-xs leading-relaxed text-slate-400">
                  Calibração em rede global de companheiros de equipe via regressão linear regularizada (Ridge/LMM), padronização em Z-Score por era, Bayesian shrinkage para amostras pequenas, decaimento exponencial e síntese dos 5 pilares na escala 0–99.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3.5 rounded-xl border border-white/10 bg-white/[0.02] p-4">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-emerald-500/15 text-emerald-400">
                <Database className="h-4 w-4" />
              </div>
              <div className="space-y-1">
                <h3 className="text-sm font-bold text-white">
                  Pipeline Híbrido FastF1 + Jolpica-F1 em FastAPI/SQLite
                </h3>
                <p className="text-xs leading-relaxed text-slate-400">
                  Ingestão contínua de voltas limpas, compostos de pneu e status de pista via FastF1 (2018+) combinada ao histórico completo desde 1950 via Jolpica-F1, servida por API FastAPI com persistência otimizada em SQLite.
                </p>
              </div>
            </div>

            <div className="flex items-start gap-3.5 rounded-xl border border-white/10 bg-white/[0.02] p-4">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-sky-500/15 text-sky-400">
                <Layers className="h-4 w-4" />
              </div>
              <div className="space-y-1">
                <h3 className="text-sm font-bold text-white">
                  Frontend Interativo React 19 + Recharts + Deploy Cloud
                </h3>
                <p className="text-xs leading-relaxed text-slate-400">
                  Interface responsiva com gráficos de telemetria e radar, comparador H2H, simulador de mundo contrafactual, sandbox de pesos ao vivo e empacotamento em Docker com deploy integrado na Vercel e no Railway.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Coluna Direita: Stack & Filosofia Open Source */}
        <div className="lg:col-span-5 rounded-2xl border border-white/10 bg-[#111520] p-6 flex flex-col justify-between space-y-6">
          <div className="space-y-4">
            <div>
              <h2 className="text-lg font-extrabold tracking-tight text-white">
                Stack &amp; Filosofia Open Source
              </h2>
              <p className="mt-1 text-xs leading-relaxed text-slate-400">
                Desenvolvido por {AUTHOR_PROFILE.name} na {AUTHOR_PROFILE.institution} com foco em engenharia limpa, reprodutibilidade científica e construção em público — combinando análise estatística em Python/TypeScript com base sólida em linguagens de baixo nível.
              </p>
            </div>

            <div className="space-y-2">
              <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
                Tecnologias &amp; Linguagens
              </div>
              <div className="flex flex-wrap gap-2">
                {AUTHOR_PROFILE.coreStack.map((tech) => (
                  <span
                    key={tech}
                    className="rounded-lg border border-white/10 bg-white/5 px-2.5 py-1 font-mono text-xs font-semibold text-slate-200"
                  >
                    {tech}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <div className="space-y-3 border-t border-white/10 pt-5">
            <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">
              Explorar a Plataforma
            </div>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {EXPLORE_LINKS.map((item) => (
                <Link
                  key={item.to}
                  to={item.to}
                  className="inline-flex items-center justify-between gap-2 rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-xs font-semibold text-slate-200 hover:border-white/20 hover:bg-white/[0.08] transition"
                >
                  <span className="truncate">{item.label}</span>
                  <ArrowUpRight className="h-3.5 w-3.5 shrink-0 text-slate-400" />
                </Link>
              ))}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
