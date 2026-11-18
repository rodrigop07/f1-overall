import {
  Legend,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';

interface RadarTarget {
  name: string;
  color: string;
  pace: number;
  qualifying: number;
  consistency: number;
  racecraft: number;
  experience: number;
}

interface PillarRadarProps {
  primary: RadarTarget;
  secondary?: RadarTarget;
  showGridBaseline?: boolean;
  height?: number;
}

export function PillarRadar({
  primary,
  secondary,
  showGridBaseline = true,
  height = 300,
}: PillarRadarProps) {
  const data = [
    {
      pillar: 'Ritmo (35%)',
      primary: Number(primary.pace.toFixed(1)),
      secondary: secondary ? Number(secondary.pace.toFixed(1)) : undefined,
      baseline: 82,
    },
    {
      pillar: 'Classif. (25%)',
      primary: Number(primary.qualifying.toFixed(1)),
      secondary: secondary ? Number(secondary.qualifying.toFixed(1)) : undefined,
      baseline: 82,
    },
    {
      pillar: 'Consist. (20%)',
      primary: Number(primary.consistency.toFixed(1)),
      secondary: secondary ? Number(secondary.consistency.toFixed(1)) : undefined,
      baseline: 82,
    },
    {
      pillar: 'Combate (15%)',
      primary: Number(primary.racecraft.toFixed(1)),
      secondary: secondary ? Number(secondary.racecraft.toFixed(1)) : undefined,
      baseline: 82,
    },
    {
      pillar: 'Experiência (5%)',
      primary: Number(primary.experience.toFixed(1)),
      secondary: secondary ? Number(secondary.experience.toFixed(1)) : undefined,
      baseline: 82,
    },
  ];

  return (
    <div style={{ width: '100%', height }}>
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart cx="50%" cy="50%" outerRadius="72%" data={data}>
          <PolarGrid stroke="#263044" />
          <PolarAngleAxis
            dataKey="pillar"
            tick={{ fill: '#cbd5e1', fontSize: 11, fontWeight: 600 }}
          />
          <PolarRadiusAxis
            angle={90}
            domain={[60, 99]}
            tickCount={5}
            tick={{ fill: '#64748b', fontSize: 10 }}
          />
          {showGridBaseline && !secondary && (
            <Radar
              name="Média do Grid (82)"
              dataKey="baseline"
              stroke="#64748b"
              strokeDasharray="4 4"
              fill="#64748b"
              fillOpacity={0.08}
            />
          )}
          <Radar
            name={primary.name}
            dataKey="primary"
            stroke={primary.color || '#E10600'}
            strokeWidth={2.5}
            fill={primary.color || '#E10600'}
            fillOpacity={0.28}
          />
          {secondary && (
            <Radar
              name={secondary.name}
              dataKey="secondary"
              stroke={secondary.color || '#38BDF8'}
              strokeWidth={2.5}
              fill={secondary.color || '#38BDF8'}
              fillOpacity={0.22}
            />
          )}
          <Tooltip
            contentStyle={{
              backgroundColor: '#0f1420',
              borderColor: 'rgba(255,255,255,0.12)',
              borderRadius: '0.75rem',
              fontSize: '12px',
            }}
          />
          <Legend wrapperStyle={{ fontSize: '12px' }} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
