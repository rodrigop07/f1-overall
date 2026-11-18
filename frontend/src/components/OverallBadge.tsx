interface OverallBadgeProps {
  score: number;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  showTier?: boolean;
}

export function getTierMeta(score: number) {
  if (score >= 93) {
    return {
      label: 'LENDÁRIO',
      textClass: 'text-amber-300',
      borderClass: 'border-amber-400/50',
      bgClass: 'bg-gradient-to-br from-amber-500/20 via-amber-400/10 to-transparent',
      glowClass: 'shadow-[0_0_24px_rgba(251,191,36,0.2)]',
      barColor: '#fbbf24',
    };
  }
  if (score >= 88) {
    return {
      label: 'SUPER ELITE',
      textClass: 'text-emerald-300',
      borderClass: 'border-emerald-400/45',
      bgClass: 'bg-gradient-to-br from-emerald-500/20 via-emerald-400/10 to-transparent',
      glowClass: 'shadow-[0_0_20px_rgba(52,211,153,0.16)]',
      barColor: '#34d399',
    };
  }
  if (score >= 83) {
    return {
      label: 'ELITE GRID',
      textClass: 'text-sky-300',
      borderClass: 'border-sky-400/40',
      bgClass: 'bg-gradient-to-br from-sky-500/15 via-sky-400/5 to-transparent',
      glowClass: '',
      barColor: '#38bdf8',
    };
  }
  if (score >= 78) {
    return {
      label: 'TITULAR',
      textClass: 'text-indigo-200',
      borderClass: 'border-indigo-400/35',
      bgClass: 'bg-gradient-to-br from-indigo-500/15 via-slate-800/40 to-transparent',
      glowClass: '',
      barColor: '#818cf8',
    };
  }
  return {
    label: 'EM DESENVOLVIMENTO',
    textClass: 'text-slate-300',
    borderClass: 'border-slate-500/40',
    bgClass: 'bg-gradient-to-br from-slate-700/30 to-transparent',
    glowClass: '',
    barColor: '#94a3b8',
  };
}

export function OverallBadge({ score, size = 'md', showTier = false }: OverallBadgeProps) {
  const tier = getTierMeta(score);
  const sizeStyles = {
    sm: 'px-2 py-0.5 text-sm rounded-md min-w-[2.25rem]',
    md: 'px-2.5 py-1 text-lg rounded-lg min-w-[2.75rem]',
    lg: 'px-3.5 py-1.5 text-3xl rounded-xl min-w-[3.75rem]',
    xl: 'px-4 py-2 text-5xl rounded-2xl min-w-[5rem]',
  }[size];

  return (
    <div className="inline-flex flex-col items-center gap-1">
      <div
        className={`inline-flex items-center justify-center border font-mono font-extrabold tracking-tight tabular-nums ${sizeStyles} ${tier.textClass} ${tier.borderClass} ${tier.bgClass} ${tier.glowClass}`}
      >
        {Math.round(score)}
      </div>
      {showTier && (
        <span className={`text-[10px] font-bold tracking-widest uppercase ${tier.textClass}`}>
          {tier.label}
        </span>
      )}
    </div>
  );
}
