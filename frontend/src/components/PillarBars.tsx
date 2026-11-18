interface PillarBarsProps {
  pace: number;
  qualifying: number;
  consistency: number;
  racecraft: number;
  experience: number;
  compact?: boolean;
}

const PILLARS = [
  { key: 'pace', abbr: 'RIT', label: 'Ritmo de Corrida', weight: '35%', color: '#E10600' },
  { key: 'qualifying', abbr: 'CLA', label: 'Classificação', weight: '25%', color: '#38BDF8' },
  { key: 'consistency', abbr: 'CON', label: 'Consistência', weight: '20%', color: '#34D399' },
  { key: 'racecraft', abbr: 'CMB', label: 'Combate', weight: '15%', color: '#FBBF24' },
  { key: 'experience', abbr: 'EXP', label: 'Experiência', weight: '5%', color: '#A78BFA' },
] as const;

export function PillarBars({
  pace,
  qualifying,
  consistency,
  racecraft,
  experience,
  compact = false,
}: PillarBarsProps) {
  const values: Record<string, number> = {
    pace,
    qualifying,
    consistency,
    racecraft,
    experience,
  };

  if (compact) {
    return (
      <div className="grid grid-cols-5 gap-1.5">
        {PILLARS.map((p) => {
          const val = values[p.key];
          return (
            <div
              key={p.key}
              className="rounded-lg bg-black/35 border border-white/5 px-1.5 py-1.5 text-center"
              title={`${p.label} (${p.weight}): ${val.toFixed(1)}`}
            >
              <div className="text-[10px] font-semibold tracking-wider text-slate-400">{p.abbr}</div>
              <div className="font-mono text-sm font-bold text-slate-100 tabular-nums">
                {Math.round(val)}
              </div>
            </div>
          );
        })}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {PILLARS.map((p) => {
        const val = values[p.key];
        const pct = Math.max(0, Math.min(100, ((val - 60) / 39) * 100));
        return (
          <div key={p.key} className="space-y-1">
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-300 font-medium">
                {p.label}{' '}
                <span className="text-slate-500 font-mono text-[11px]">({p.weight})</span>
              </span>
              <span className="font-mono font-bold text-white tabular-nums">
                {val.toFixed(1)}
              </span>
            </div>
            <div className="h-2 w-full rounded-full bg-slate-800/90 overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{ width: `${pct}%`, backgroundColor: p.color }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}
