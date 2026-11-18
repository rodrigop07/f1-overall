import { Link } from 'react-router-dom';
import { Award, ShieldAlert } from 'lucide-react';
import { getTierMeta, OverallBadge } from './OverallBadge';
import { PillarBars } from './PillarBars';

interface DriverCardProps {
  rank?: number;
  reference: string;
  name: string;
  abbreviation?: string | null;
  nationality?: string | null;
  teamName: string;
  teamColor: string;
  overall: number;
  overallRaw?: number;
  pace: number;
  qualifying: number;
  consistency: number;
  racecraft: number;
  experience: number;
  racesCount: number;
  carRating?: number;
  championships?: number;
  shrinkageWeight?: number;
  subtitle?: string;
}

export function dataTierLabel(tier: string): string {
  switch (tier) {
    case 'TELEMETRY_COMPOUND':
      return 'Telemetria + Compostos';
    case 'LAP_BY_LAP':
      return 'Volta a Volta (Clean Air)';
    default:
      return 'Histórico Clássico';
  }
}

export function DriverCard({
  rank,
  reference,
  name,
  abbreviation,
  nationality,
  teamName,
  teamColor,
  overall,
  overallRaw,
  pace,
  qualifying,
  consistency,
  racecraft,
  experience,
  racesCount,
  carRating,
  championships,
  shrinkageWeight,
  subtitle,
}: DriverCardProps) {
  const tier = getTierMeta(overall);
  const isShrunk = shrinkageWeight !== undefined && shrinkageWeight < 0.7;

  return (
    <Link
      to={`/drivers/${reference}`}
      className={`group relative block overflow-hidden rounded-2xl border bg-[#111520] p-5 transition-all duration-200 hover:-translate-y-0.5 hover:bg-[#151a28] ${tier.borderClass} ${tier.glowClass}`}
    >
      {/* Top team color accent */}
      <div
        className="absolute inset-x-0 top-0 h-1.5"
        style={{ backgroundColor: teamColor || '#E10600' }}
      />

      <div className="flex items-start justify-between gap-4 pt-1">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            {rank !== undefined && (
              <span className="inline-flex h-6 min-w-6 items-center justify-center rounded-md bg-white/10 px-1.5 font-mono text-xs font-bold text-slate-200">
                #{rank}
              </span>
            )}
            {abbreviation && (
              <span className="font-mono text-xs font-bold tracking-widest text-slate-400">
                {abbreviation}
              </span>
            )}
            {championships !== undefined && championships > 0 && (
              <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-bold text-amber-300 border border-amber-400/30">
                <Award className="h-3 w-3" /> {championships}x WDC
              </span>
            )}
          </div>

          <h3 className="mt-2 truncate text-lg font-extrabold tracking-tight text-white group-hover:text-red-400 transition-colors">
            {name}
          </h3>
          <p className="text-xs font-medium text-slate-400 truncate">
            <span
              className="inline-block h-2 w-2 rounded-full mr-1.5 align-middle"
              style={{ backgroundColor: teamColor || '#94A3B8' }}
            />
            {teamName}
            {nationality ? ` · ${nationality}` : ''}
          </p>
          {subtitle && <p className="mt-0.5 text-[11px] text-slate-500">{subtitle}</p>}
        </div>

        <div className="shrink-0 text-right">
          <OverallBadge score={overall} size="lg" showTier />
          {overallRaw !== undefined && (
            <div className="mt-1 font-mono text-[10px] text-slate-500 tabular-nums">
              exact {overallRaw.toFixed(2)}
            </div>
          )}
        </div>
      </div>

      <div className="mt-4">
        <PillarBars
          compact
          pace={pace}
          qualifying={qualifying}
          consistency={consistency}
          racecraft={racecraft}
          experience={experience}
        />
      </div>

      <div className="mt-3 flex items-center justify-between text-[11px] text-slate-400 border-t border-white/5 pt-2.5">
        <span className="font-mono tabular-nums">{racesCount} GPs na amostra</span>
        <div className="flex items-center gap-2">
          {isShrunk && (
            <span
              className="inline-flex items-center gap-1 text-amber-300/90"
              title={`Bayesian Shrinkage ativo (confiança ${(shrinkageWeight! * 100).toFixed(0)}%)`}
            >
              <ShieldAlert className="h-3 w-3" /> Shrinkage
            </span>
          )}
          {carRating !== undefined && (
            <span className="font-mono tabular-nums">
              Carro <strong className="text-slate-200">{carRating.toFixed(1)}</strong>
            </span>
          )}
        </div>
      </div>
    </Link>
  );
}
