import { useState } from 'react';
import { Download } from 'lucide-react';

export interface DriverExportData {
  mode: 'driver';
  name: string;
  reference: string;
  teamName: string;
  teamColor: string;
  nationality?: string | null;
  overall: number;
  overallRaw?: number;
  overallCi?: number;
  subtitle: string;
  pillars: {
    pace: number;
    qualifying: number;
    consistency: number;
    racecraft: number;
    experience: number;
  };
  specialties?: {
    wet: number;
    street: number;
    highSpeed: number;
    tyre: number;
  };
  badges?: string[];
  stats?: Array<{ label: string; value: string }>;
}

export interface CompareExportData {
  mode: 'compare';
  subtitle: string;
  driverA: {
    name: string;
    teamName: string;
    teamColor: string;
    overall: number;
    pace: number;
    qualifying: number;
    consistency: number;
    racecraft: number;
    experience: number;
  };
  driverB: {
    name: string;
    teamName: string;
    teamColor: string;
    overall: number;
    pace: number;
    qualifying: number;
    consistency: number;
    racecraft: number;
    experience: number;
  };
}

type ExportCardProps =
  | { data: DriverExportData; label?: string }
  | { data: CompareExportData; label?: string };

function roundRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number
) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function getScoreHex(score: number): string {
  if (score >= 93) return '#F59E0B';
  if (score >= 86) return '#10B981';
  if (score >= 78) return '#3B82F6';
  return '#94A3B8';
}

function renderDriverCardCanvas(d: DriverExportData): string {
  const W = 1200;
  const H = 640;
  const canvas = document.createElement('canvas');
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext('2d')!;

  // Background
  const bg = ctx.createLinearGradient(0, 0, W, H);
  bg.addColorStop(0, '#090B10');
  bg.addColorStop(1, '#121826');
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, W, H);

  // Subtle team accent glow
  ctx.fillStyle = d.teamColor || '#E10600';
  ctx.fillRect(0, 0, W, 10);

  // Header brand
  ctx.fillStyle = '#E10600';
  roundRect(ctx, 52, 42, 42, 42, 10);
  ctx.fill();
  ctx.fillStyle = '#FFFFFF';
  ctx.font = '900 18px Inter, system-ui, sans-serif';
  ctx.fillText('F1', 62, 69);

  ctx.fillStyle = '#F8FAFC';
  ctx.font = '800 20px Inter, system-ui, sans-serif';
  ctx.fillText('F1 OVERALL · ISOLAMENTO PILOTO VS. CARRO', 110, 62);
  ctx.fillStyle = '#94A3B8';
  ctx.font = '500 14px Inter, system-ui, sans-serif';
  ctx.fillText(d.subtitle, 110, 84);

  // Driver Name
  ctx.fillStyle = '#FFFFFF';
  ctx.font = '900 54px Inter, system-ui, sans-serif';
  ctx.fillText(d.name, 52, 175);

  ctx.fillStyle = d.teamColor || '#94A3B8';
  ctx.beginPath();
  ctx.arc(62, 206, 6, 0, Math.PI * 2);
  ctx.fill();

  ctx.fillStyle = '#CBD5E1';
  ctx.font = '600 20px Inter, system-ui, sans-serif';
  ctx.fillText(`${d.teamName}${d.nationality ? ` · ${d.nationality}` : ''}`, 80, 213);

  // Big Overall Box
  const ovrColor = getScoreHex(d.overall);
  ctx.fillStyle = '#151B29';
  roundRect(ctx, 900, 56, 248, 176, 20);
  ctx.fill();
  ctx.strokeStyle = ovrColor;
  ctx.lineWidth = 3;
  ctx.stroke();

  ctx.fillStyle = '#94A3B8';
  ctx.font = '700 14px Inter, system-ui, sans-serif';
  ctx.fillText('OVERALL (0–99)', 958, 92);

  ctx.fillStyle = ovrColor;
  ctx.font = '900 92px Inter, system-ui, sans-serif';
  ctx.fillText(String(d.overall), 968, 182);

  if (d.overallRaw !== undefined) {
    ctx.fillStyle = '#94A3B8';
    ctx.font = '600 14px monospace';
    const ciTxt = d.overallCi ? ` ± ${d.overallCi.toFixed(1)}` : '';
    ctx.fillText(`${d.overallRaw.toFixed(2)}${ciTxt}`, 965, 212);
  }

  // Pillars Card
  ctx.fillStyle = '#111622';
  roundRect(ctx, 52, 255, 650, 285, 18);
  ctx.fill();
  ctx.strokeStyle = 'rgba(255,255,255,0.08)';
  ctx.lineWidth = 1.5;
  ctx.stroke();

  const pillarRows = [
    { label: 'Ritmo de Corrida (35%)', val: d.pillars.pace, color: '#EF4444' },
    { label: 'Classificação (25%)', val: d.pillars.qualifying, color: '#3B82F6' },
    { label: 'Consistência (20%)', val: d.pillars.consistency, color: '#10B981' },
    { label: 'Combate / Racecraft (15%)', val: d.pillars.racecraft, color: '#F59E0B' },
    { label: 'Experiência (5%)', val: d.pillars.experience, color: '#A855F7' },
  ];

  pillarRows.forEach((p, idx) => {
    const y = 298 + idx * 50;
    ctx.fillStyle = '#CBD5E1';
    ctx.font = '600 16px Inter, system-ui, sans-serif';
    ctx.fillText(p.label, 78, y);

    ctx.fillStyle = '#FFFFFF';
    ctx.font = '800 18px monospace';
    ctx.fillText(p.val.toFixed(1), 626, y);

    // Bar bg
    ctx.fillStyle = '#1E2538';
    roundRect(ctx, 320, y - 14, 285, 14, 7);
    ctx.fill();

    // Bar fill
    const pct = Math.max(0.05, Math.min(1, (p.val - 55) / 44));
    ctx.fillStyle = p.color;
    roundRect(ctx, 320, y - 14, Math.max(16, 285 * pct), 14, 7);
    ctx.fill();
  });

  // Right column: Specialties & Stats
  ctx.fillStyle = '#111622';
  roundRect(ctx, 730, 255, 418, 285, 18);
  ctx.fill();
  ctx.strokeStyle = 'rgba(255,255,255,0.08)';
  ctx.stroke();

  ctx.fillStyle = '#94A3B8';
  ctx.font = '700 14px Inter, system-ui, sans-serif';
  ctx.fillText('ESPECIALIDADES & TELEMETRIA', 756, 290);

  if (d.specialties) {
    const specs = [
      { label: 'Chuva', val: d.specialties.wet },
      { label: 'Circuitos de Rua', val: d.specialties.street },
      { label: 'Alta Velocidade', val: d.specialties.highSpeed },
      { label: 'Gestão de Pneus', val: d.specialties.tyre },
    ];
    specs.forEach((s, idx) => {
      const col = idx % 2;
      const row = Math.floor(idx / 2);
      const sx = 756 + col * 190;
      const sy = 312 + row * 70;
      ctx.fillStyle = '#192030';
      roundRect(ctx, sx, sy, 174, 56, 10);
      ctx.fill();
      ctx.fillStyle = '#94A3B8';
      ctx.font = '600 12px Inter, system-ui, sans-serif';
      ctx.fillText(s.label, sx + 12, sy + 22);
      ctx.fillStyle = getScoreHex(s.val);
      ctx.font = '900 22px monospace';
      ctx.fillText(s.val.toFixed(1), sx + 12, sy + 46);
    });
  }

  if (d.stats && d.stats.length > 0) {
    d.stats.slice(0, 3).forEach((st, idx) => {
      const sx = 756 + idx * 128;
      const sy = 468;
      ctx.fillStyle = '#94A3B8';
      ctx.font = '600 12px Inter, system-ui, sans-serif';
      ctx.fillText(st.label, sx, sy);
      ctx.fillStyle = '#F8FAFC';
      ctx.font = '800 20px Inter, system-ui, sans-serif';
      ctx.fillText(st.value, sx, sy + 26);
    });
  }

  // Badges footer
  if (d.badges && d.badges.length > 0) {
    let bx = 52;
    ctx.font = '700 13px Inter, system-ui, sans-serif';
    d.badges.slice(0, 4).forEach((badge) => {
      const bw = ctx.measureText(badge).width + 26;
      ctx.fillStyle = 'rgba(245, 158, 11, 0.14)';
      roundRect(ctx, bx, 566, bw, 32, 16);
      ctx.fill();
      ctx.strokeStyle = 'rgba(245, 158, 11, 0.45)';
      ctx.stroke();
      ctx.fillStyle = '#FCD34D';
      ctx.fillText(badge, bx + 13, 587);
      bx += bw + 12;
    });
  }

  ctx.fillStyle = '#64748B';
  ctx.font = '500 13px monospace';
  ctx.fillText('f1-overall · Ridge LMM + Clean Air + FastF1/Jolpica', 745, 588);

  return canvas.toDataURL('image/png');
}

function renderCompareCardCanvas(c: CompareExportData): string {
  const W = 1200;
  const H = 640;
  const canvas = document.createElement('canvas');
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext('2d')!;

  const bg = ctx.createLinearGradient(0, 0, W, H);
  bg.addColorStop(0, '#090B10');
  bg.addColorStop(1, '#121826');
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, W, H);

  ctx.fillStyle = c.driverA.teamColor || '#E10600';
  ctx.fillRect(0, 0, W / 2, 10);
  ctx.fillStyle = c.driverB.teamColor || '#3B82F6';
  ctx.fillRect(W / 2, 0, W / 2, 10);

  ctx.fillStyle = '#F8FAFC';
  ctx.font = '900 24px Inter, system-ui, sans-serif';
  ctx.fillText('COMPARADOR HEAD-TO-HEAD · F1 OVERALL', 52, 62);
  ctx.fillStyle = '#94A3B8';
  ctx.font = '500 15px Inter, system-ui, sans-serif';
  ctx.fillText(c.subtitle, 52, 86);

  // Driver A header
  ctx.fillStyle = '#FFFFFF';
  ctx.font = '900 34px Inter, system-ui, sans-serif';
  ctx.fillText(c.driverA.name, 52, 155);
  ctx.fillStyle = '#94A3B8';
  ctx.font = '600 16px Inter, system-ui, sans-serif';
  ctx.fillText(c.driverA.teamName, 52, 182);
  ctx.fillStyle = getScoreHex(c.driverA.overall);
  ctx.font = '900 64px Inter, system-ui, sans-serif';
  ctx.fillText(String(c.driverA.overall), 445, 174);

  // VS divider
  ctx.fillStyle = '#E10600';
  ctx.font = '900 22px Inter, system-ui, sans-serif';
  ctx.fillText('VS', 584, 165);

  // Driver B header
  ctx.fillStyle = getScoreHex(c.driverB.overall);
  ctx.font = '900 64px Inter, system-ui, sans-serif';
  ctx.fillText(String(c.driverB.overall), 665, 174);
  ctx.fillStyle = '#FFFFFF';
  ctx.font = '900 34px Inter, system-ui, sans-serif';
  ctx.fillText(c.driverB.name, 770, 155);
  ctx.fillStyle = '#94A3B8';
  ctx.font = '600 16px Inter, system-ui, sans-serif';
  ctx.fillText(c.driverB.teamName, 770, 182);

  // Comparison bars
  ctx.fillStyle = '#111622';
  roundRect(ctx, 52, 225, 1096, 350, 18);
  ctx.fill();
  ctx.strokeStyle = 'rgba(255,255,255,0.08)';
  ctx.stroke();

  const metrics: Array<{ label: string; a: number; b: number }> = [
    { label: 'Ritmo de Corrida (35%)', a: c.driverA.pace, b: c.driverB.pace },
    { label: 'Classificação (25%)', a: c.driverA.qualifying, b: c.driverB.qualifying },
    { label: 'Consistência (20%)', a: c.driverA.consistency, b: c.driverB.consistency },
    { label: 'Combate / Racecraft (15%)', a: c.driverA.racecraft, b: c.driverB.racecraft },
    { label: 'Experiência (5%)', a: c.driverA.experience, b: c.driverB.experience },
  ];

  metrics.forEach((m, idx) => {
    const y = 278 + idx * 62;
    ctx.fillStyle = '#94A3B8';
    ctx.font = '600 15px Inter, system-ui, sans-serif';
    ctx.fillText(m.label, 495, y);

    ctx.fillStyle = m.a >= m.b ? '#FFFFFF' : '#94A3B8';
    ctx.font = '800 22px monospace';
    ctx.fillText(m.a.toFixed(1), 85, y + 4);

    ctx.fillStyle = m.b >= m.a ? '#FFFFFF' : '#94A3B8';
    ctx.fillText(m.b.toFixed(1), 1045, y + 4);

    const aPct = Math.max(0.06, Math.min(1, (m.a - 55) / 44));
    const bPct = Math.max(0.06, Math.min(1, (m.b - 55) / 44));
    ctx.fillStyle = '#1D2436';
    roundRect(ctx, 165, y - 12, 290, 14, 7);
    ctx.fill();
    roundRect(ctx, 725, y - 12, 290, 14, 7);
    ctx.fill();

    ctx.fillStyle = c.driverA.teamColor || '#EF4444';
    const aw = 290 * aPct;
    roundRect(ctx, 165 + (290 - aw), y - 12, aw, 14, 7);
    ctx.fill();

    ctx.fillStyle = c.driverB.teamColor || '#3B82F6';
    roundRect(ctx, 725, y - 12, 290 * bPct, 14, 7);
    ctx.fill();
  });

  ctx.fillStyle = '#64748B';
  ctx.font = '500 13px monospace';
  ctx.fillText('f1-overall · Isolamento Estatístico Piloto vs. Carro (1950–2026)', 52, 608);

  return canvas.toDataURL('image/png');
}

export function ExportCardButton({ data, label = 'Baixar Card PNG' }: ExportCardProps) {
  const [busy, setBusy] = useState(false);

  const handleExport = () => {
    setBusy(true);
    try {
      const dataUrl =
        data.mode === 'driver' ? renderDriverCardCanvas(data) : renderCompareCardCanvas(data);
      const a = document.createElement('a');
      a.href = dataUrl;
      a.download =
        data.mode === 'driver'
          ? `${data.reference}-f1-overall.png`
          : `h2h-${data.driverA.name.toLowerCase().replace(/\s+/g, '-')}-vs-${data.driverB.name.toLowerCase().replace(/\s+/g, '-')}.png`;
      a.click();
    } finally {
      setTimeout(() => setBusy(false), 300);
    }
  };

  return (
    <button
      type="button"
      onClick={handleExport}
      disabled={busy}
      className="inline-flex items-center gap-1.5 rounded-xl border border-white/15 bg-white/5 px-3 py-2 text-xs font-bold text-slate-200 hover:bg-white/10 hover:text-white transition-colors cursor-pointer disabled:opacity-50"
    >
      <Download className="h-3.5 w-3.5 text-red-400" />
      {busy ? 'Gerando PNG...' : label}
    </button>
  );
}
