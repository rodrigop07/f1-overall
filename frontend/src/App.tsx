import { lazy, Suspense, useEffect, useState } from 'react';
import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { CommandPalette } from './components/CommandPalette';
import { Navbar } from './components/Navbar';

const SeasonRankingsPage = lazy(() =>
  import('./pages/SeasonRankingsPage').then((m) => ({ default: m.SeasonRankingsPage }))
);
const AllTimeRankingsPage = lazy(() =>
  import('./pages/AllTimeRankingsPage').then((m) => ({ default: m.AllTimeRankingsPage }))
);
const DriverProfilePage = lazy(() =>
  import('./pages/DriverProfilePage').then((m) => ({ default: m.DriverProfilePage }))
);
const ComparePage = lazy(() =>
  import('./pages/ComparePage').then((m) => ({ default: m.ComparePage }))
);
const NetworkPage = lazy(() =>
  import('./pages/NetworkPage').then((m) => ({ default: m.NetworkPage }))
);
const SandboxPage = lazy(() =>
  import('./pages/SandboxPage').then((m) => ({ default: m.SandboxPage }))
);
const RaceExplorerPage = lazy(() =>
  import('./pages/RaceExplorerPage').then((m) => ({ default: m.RaceExplorerPage }))
);
const TeamsLineagePage = lazy(() =>
  import('./pages/TeamsLineagePage').then((m) => ({ default: m.TeamsLineagePage }))
);
const WhatIfPage = lazy(() =>
  import('./pages/WhatIfPage').then((m) => ({ default: m.WhatIfPage }))
);

function RouteFallback() {
  return (
    <div className="space-y-4">
      <div className="h-32 animate-pulse rounded-2xl bg-white/5" />
      <div className="h-72 animate-pulse rounded-2xl bg-white/5" />
    </div>
  );
}

export function App() {
  const [searchOpen, setSearchOpen] = useState(false);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setSearchOpen((prev) => !prev);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  return (
    <BrowserRouter>
      <div className="min-h-screen bg-[#090B10] text-slate-100">
        <Navbar onOpenSearch={() => setSearchOpen(true)} />
        <CommandPalette open={searchOpen} onClose={() => setSearchOpen(false)} />
        <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 sm:py-8">
          <Suspense fallback={<RouteFallback />}>
            <Routes>
              <Route path="/" element={<SeasonRankingsPage />} />
              <Route path="/all-time" element={<AllTimeRankingsPage />} />
              <Route path="/drivers/:driverRef" element={<DriverProfilePage />} />
              <Route path="/compare" element={<ComparePage />} />
              <Route path="/network" element={<NetworkPage />} />
              <Route path="/sandbox" element={<SandboxPage />} />
              <Route path="/races" element={<RaceExplorerPage />} />
              <Route path="/races/:year/:roundNumber" element={<RaceExplorerPage />} />
              <Route path="/teams" element={<TeamsLineagePage />} />
              <Route path="/teams/:slug" element={<TeamsLineagePage />} />
              <Route path="/what-if" element={<WhatIfPage />} />
            </Routes>
          </Suspense>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
