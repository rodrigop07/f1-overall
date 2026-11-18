import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Network, Route, Search } from 'lucide-react';
import { api } from '../api/client';
import { OverallBadge } from '../components/OverallBadge';
import type { DriverSummary, NetworkNode, NetworkResponse } from '../types/f1';

interface PositionedNode extends NetworkNode {
  x: number;
  y: number;
}

const DECADES = [
  { label: 'Elite Global (1950–2026)', value: null },
  { label: '2020s', value: 2020 },
  { label: '2010s', value: 2010 },
  { label: '2000s', value: 2000 },
  { label: '1990s', value: 1990 },
  { label: '1980s', value: 1980 },
  { label: '1970s', value: 1970 },
  { label: '1960s', value: 1960 },
  { label: '1950s', value: 1950 },
];

export function NetworkPage() {
  const [allDrivers, setAllDrivers] = useState<DriverSummary[]>([]);
  const [centerDriver, setCenterDriver] = useState<string>('');
  const [decade, setDecade] = useState<number | null>(2020);
  const [minShared, setMinShared] = useState<number>(8);
  const [pathFrom, setPathFrom] = useState<string>('senna');
  const [pathTo, setPathTo] = useState<string>('max_verstappen');
  const [data, setData] = useState<NetworkResponse | null>(null);
  const [selectedNode, setSelectedNode] = useState<NetworkNode | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getDriversList().then((res) => setAllDrivers(res.drivers)).catch(() => {});
  }, []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .getNetwork({
        center_driver: centerDriver || undefined,
        decade: centerDriver ? null : decade,
        min_shared_races: minShared,
        path_from: pathFrom || undefined,
        path_to: pathTo || undefined,
        max_nodes: 70,
      })
      .then((res) => {
        if (!cancelled) {
          setData(res);
          if (res.nodes.length > 0 && !selectedNode) {
            setSelectedNode(res.nodes[0]);
          }
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [centerDriver, decade, minShared, pathFrom, pathTo]);

  // Deterministic force-directed layout in pure TypeScript
  const layout = useMemo(() => {
    if (!data || data.nodes.length === 0) {
      return { nodes: [] as PositionedNode[], nodeMap: new Map<number, PositionedNode>() };
    }
    const W = 900;
    const H = 560;
    const n = data.nodes.length;

    const pos = data.nodes.map((node, i) => {
      const angle = (2 * Math.PI * i) / n;
      const r = 180 + (i % 3) * 35;
      return {
        ...node,
        x: W / 2 + r * Math.cos(angle),
        y: H / 2 + r * Math.sin(angle),
      };
    });

    const idxMap = new Map<number, number>();
    pos.forEach((p, idx) => idxMap.set(p.driver_id, idx));

    const dispX = new Float64Array(n);
    const dispY = new Float64Array(n);
    const k = Math.sqrt((W * H) / Math.max(n, 1)) * 0.85;

    for (let iter = 0; iter < 110; iter++) {
      dispX.fill(0);
      dispY.fill(0);
      const temp = 18.0 * (1 - iter / 115);

      // Repulsion
      for (let i = 0; i < n; i++) {
        for (let j = i + 1; j < n; j++) {
          const dx = pos[i].x - pos[j].x;
          const dy = pos[i].y - pos[j].y;
          const dist = Math.hypot(dx, dy) + 0.01;
          const force = (k * k) / dist;
          const fx = (dx / dist) * force;
          const fy = (dy / dist) * force;
          dispX[i] += fx;
          dispY[i] += fy;
          dispX[j] -= fx;
          dispY[j] -= fy;
        }
      }

      // Attraction along edges
      for (const e of data.edges) {
        const i = idxMap.get(e.source);
        const j = idxMap.get(e.target);
        if (i === undefined || j === undefined) continue;
        const dx = pos[i].x - pos[j].x;
        const dy = pos[i].y - pos[j].y;
        const dist = Math.hypot(dx, dy) + 0.01;
        const strength = e.in_shortest_path ? 1.8 : 1.0;
        const force = ((dist * dist) / k) * 0.45 * strength;
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        dispX[i] -= fx;
        dispY[i] -= fy;
        dispX[j] += fx;
        dispY[j] += fy;
      }

      // Mild gravity to center
      for (let i = 0; i < n; i++) {
        dispX[i] += (W / 2 - pos[i].x) * 0.08;
        dispY[i] += (H / 2 - pos[i].y) * 0.08;

        const d = Math.hypot(dispX[i], dispY[i]) + 0.01;
        const step = Math.min(d, temp);
        pos[i].x = Math.max(48, Math.min(W - 48, pos[i].x + (dispX[i] / d) * step));
        pos[i].y = Math.max(42, Math.min(H - 42, pos[i].y + (dispY[i] / d) * step));
      }
    }

    const nodeMap = new Map<number, PositionedNode>();
    pos.forEach((p) => nodeMap.set(p.driver_id, p));
    return { nodes: pos, nodeMap };
  }, [data]);

  const topDriversSelect = useMemo(() => allDrivers.slice(0, 200), [allDrivers]);

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-white/10 bg-gradient-to-br from-[#141927] via-[#0e121c] to-[#090B10] p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="inline-flex items-center gap-2 rounded-full border border-sky-400/40 bg-sky-500/10 px-3 py-1 text-[11px] font-bold uppercase tracking-wider text-sky-300">
              <Network className="h-3.5 w-3.5" /> Calibração em Rede (Força do Companheiro)
            </div>
            <h1 className="mt-2 text-2xl font-black tracking-tight text-white sm:text-3xl">
              Grafo Histórico de Companheiros de Equipe
            </h1>
            <p className="mt-1 text-sm text-slate-400">
              Cada aresta conecta dois pilotos que dividiram a mesma equipe. É essa malha que permite ao modelo LMM comparar eras distintas.
            </p>
          </div>
          {data && (
            <div className="flex gap-3 text-xs">
              <div className="rounded-xl border border-white/10 bg-black/40 px-3.5 py-2 text-center">
                <div className="text-slate-400">Nós Visíveis</div>
                <div className="font-mono text-lg font-bold text-white">{data.nodes.length}</div>
              </div>
              <div className="rounded-xl border border-white/10 bg-black/40 px-3.5 py-2 text-center">
                <div className="text-slate-400">Duelos (Arestas)</div>
                <div className="font-mono text-lg font-bold text-white">{data.edges.length}</div>
              </div>
            </div>
          )}
        </div>

        {/* Controls */}
        <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-2 lg:grid-cols-4">
          <div className="space-y-1">
            <label className="text-[11px] font-bold uppercase text-slate-400">
              Focar Ego-Network de Piloto
            </label>
            <div className="relative">
              <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-500" />
              <select
                value={centerDriver}
                onChange={(e) => setCenterDriver(e.target.value)}
                className="w-full rounded-xl border border-white/10 bg-[#090B10] py-2 pl-8 pr-3 text-xs text-white"
              >
                <option value="">Visão Geral por Era</option>
                {topDriversSelect.map((d) => (
                  <option key={d.driver_id} value={d.reference}>
                    {d.name} ({d.first_year}–{d.last_year})
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-[11px] font-bold uppercase text-slate-400">Era / Década</label>
            <select
              value={decade ?? ''}
              disabled={Boolean(centerDriver)}
              onChange={(e) => setDecade(e.target.value ? Number(e.target.value) : null)}
              className="w-full rounded-xl border border-white/10 bg-[#090B10] px-3 py-2 text-xs text-white disabled:opacity-40"
            >
              {DECADES.map((d) => (
                <option key={d.label} value={d.value ?? ''}>
                  {d.label}
                </option>
              ))}
            </select>
          </div>

          <div className="space-y-1">
            <label className="text-[11px] font-bold uppercase text-slate-400">
              Ponte Origem → Destino
            </label>
            <div className="grid grid-cols-2 gap-1.5">
              <select
                value={pathFrom}
                onChange={(e) => setPathFrom(e.target.value)}
                className="rounded-xl border border-white/10 bg-[#090B10] px-2 py-2 text-xs text-white"
              >
                <option value="">De...</option>
                {topDriversSelect.map((d) => (
                  <option key={d.driver_id} value={d.reference}>
                    {d.name}
                  </option>
                ))}
              </select>
              <select
                value={pathTo}
                onChange={(e) => setPathTo(e.target.value)}
                className="rounded-xl border border-white/10 bg-[#090B10] px-2 py-2 text-xs text-white"
              >
                <option value="">Até...</option>
                {topDriversSelect.map((d) => (
                  <option key={d.driver_id} value={d.reference}>
                    {d.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="space-y-1">
            <label className="text-[11px] font-bold uppercase text-slate-400">
              Mín. GPs Juntos: <span className="font-mono text-white">{minShared}</span>
            </label>
            <input
              type="range"
              min={1}
              max={25}
              value={minShared}
              onChange={(e) => setMinShared(Number(e.target.value))}
              className="mt-2 w-full accent-[#E10600]"
            />
          </div>
        </div>
      </section>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-4">
        {/* Interactive SVG Graph */}
        <section className="xl:col-span-3 rounded-2xl border border-white/10 bg-[#0c1019] p-3 overflow-hidden">
          {loading ? (
            <div className="h-[560px] animate-pulse rounded-xl bg-white/5" />
          ) : (
            <svg viewBox="0 0 900 560" className="w-full h-auto select-none">
              {/* Edges */}
              {data?.edges.map((e) => {
                const s = layout.nodeMap.get(e.source);
                const t = layout.nodeMap.get(e.target);
                if (!s || !t) return null;
                return (
                  <line
                    key={`${e.source}-${e.target}`}
                    x1={s.x}
                    y1={s.y}
                    x2={t.x}
                    y2={t.y}
                    stroke={e.in_shortest_path ? '#E10600' : '#2a344c'}
                    strokeWidth={e.in_shortest_path ? 3 : Math.min(2.4, 0.7 + e.shared_races / 35)}
                    strokeOpacity={e.in_shortest_path ? 0.95 : 0.65}
                  />
                );
              })}

              {/* Nodes */}
              {layout.nodes.map((node) => {
                const isSelected = selectedNode?.driver_id === node.driver_id;
                const isPathNode = data?.shortest_path.some(
                  (h) => h.from.driver_id === node.driver_id || h.to.driver_id === node.driver_id
                );
                const r = Math.max(9, Math.min(18, 7 + (node.overall - 72) * 0.45));
                return (
                  <g
                    key={node.driver_id}
                    transform={`translate(${node.x}, ${node.y})`}
                    onClick={() => setSelectedNode(node)}
                    className="cursor-pointer"
                  >
                    <circle
                      r={r}
                      fill={node.team_color || '#64748b'}
                      fillOpacity={0.9}
                      stroke={isSelected ? '#ffffff' : isPathNode ? '#E10600' : '#090B10'}
                      strokeWidth={isSelected || isPathNode ? 2.5 : 1.5}
                    />
                    <text
                      y={-r - 4}
                      textAnchor="middle"
                      fill={isPathNode || isSelected ? '#ffffff' : '#cbd5e1'}
                      fontSize={isPathNode || isSelected ? 11 : 9.5}
                      fontWeight={isPathNode || isSelected ? 700 : 500}
                    >
                      {node.abbreviation || node.name.split(' ').slice(-1)[0]}
                    </text>
                  </g>
                );
              })}
            </svg>
          )}
        </section>

        {/* Inspector Sidebar */}
        <aside className="space-y-4">
          {selectedNode && (
            <div className="rounded-2xl border border-white/10 bg-[#111520] p-5 space-y-3">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <span className="text-[11px] font-bold uppercase text-slate-400">
                    Nó Selecionado
                  </span>
                  <h3 className="text-lg font-extrabold text-white">{selectedNode.name}</h3>
                  <p className="text-xs text-slate-400">
                    {selectedNode.team_name} · {selectedNode.first_year}–{selectedNode.last_year}
                  </p>
                </div>
                <OverallBadge score={selectedNode.overall} size="md" />
              </div>

              <div className="grid grid-cols-3 gap-2 text-center text-xs pt-1">
                <div className="rounded-lg bg-black/35 p-2">
                  <div className="text-slate-500">GPs</div>
                  <div className="font-mono font-bold text-white">{selectedNode.career_starts}</div>
                </div>
                <div className="rounded-lg bg-black/35 p-2">
                  <div className="text-slate-500">Vitórias</div>
                  <div className="font-mono font-bold text-white">{selectedNode.career_wins}</div>
                </div>
                <div className="rounded-lg bg-black/35 p-2">
                  <div className="text-slate-500">Títulos</div>
                  <div className="font-mono font-bold text-amber-300">{selectedNode.championships}</div>
                </div>
              </div>

              <div className="flex flex-col gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setCenterDriver(selectedNode.reference)}
                  className="w-full rounded-xl bg-white/10 px-3 py-2 text-xs font-bold text-white hover:bg-white/20"
                >
                  Focar Rede de Companheiros
                </button>
                <Link
                  to={`/drivers/${selectedNode.reference}`}
                  className="w-full rounded-xl bg-[#E10600] px-3 py-2 text-center text-xs font-bold text-white hover:bg-red-600"
                >
                  Abrir Perfil Completo
                </Link>
              </div>
            </div>
          )}

          {data && data.shortest_path.length > 0 && (
            <div className="rounded-2xl border border-red-500/30 bg-[#111520] p-5 space-y-3">
              <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-red-400">
                <Route className="h-4 w-4" /> Ponte Destacada ({data.shortest_path.length} elos)
              </div>
              <div className="space-y-2">
                {data.shortest_path.map((hop, i) => (
                  <div key={i} className="rounded-xl border border-white/10 bg-black/35 p-2.5 text-xs">
                    <div className="font-bold text-white">
                      {hop.from.name} → {hop.to.name}
                    </div>
                    <div className="text-[11px] text-slate-400">
                      {hop.teams.join(', ')} · {hop.shared_races} GPs
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
