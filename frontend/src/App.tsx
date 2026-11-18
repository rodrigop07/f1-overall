import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { Navbar } from './components/Navbar';
import { AllTimeRankingsPage } from './pages/AllTimeRankingsPage';
import { ComparePage } from './pages/ComparePage';
import { DriverProfilePage } from './pages/DriverProfilePage';
import { NetworkPage } from './pages/NetworkPage';
import { SandboxPage } from './pages/SandboxPage';
import { SeasonRankingsPage } from './pages/SeasonRankingsPage';

export function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-[#090B10] text-slate-100 flex flex-col">
        <Navbar />
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 sm:py-8">
          <Routes>
            <Route path="/" element={<SeasonRankingsPage />} />
            <Route path="/all-time" element={<AllTimeRankingsPage />} />
            <Route path="/drivers/:driverRef" element={<DriverProfilePage />} />
            <Route path="/compare" element={<ComparePage />} />
            <Route path="/network" element={<NetworkPage />} />
            <Route path="/sandbox" element={<SandboxPage />} />
          </Routes>
        </main>
        <footer className="border-t border-white/5 py-5 text-center text-xs text-slate-500">
          F1 Overall · Dados Jolpica-F1 (1950–2026), OpenF1 & FastF1 · Modelo LMM + Bayesian Shrinkage + Z-Score (60–99)
        </footer>
      </div>
    </BrowserRouter>
  );
}

export default App;
