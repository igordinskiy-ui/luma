import { createRoot } from 'react-dom/client';
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import '@fontsource-variable/lora/wght.css';
import '@fontsource-variable/lora/wght-italic.css';
import '@fontsource-variable/manrope/wght.css';
import { App } from './features/app/App';
import { CopingFlow } from './features/coping/CopingFlow';
import { PathShowcase } from './features/design/PathShowcase';
import {
  copingTechniquesDemo,
  journalDemo,
  journalUpdateDemo,
  journeyDashboardDemo,
  journeyLastPackDemo,
  journeyPausedDemo,
  journeyPreparationDemo,
  journeyRecoveryDemo,
} from './features/design/demoFixtures';
import { FeedbackView } from './features/feedback/FeedbackView';
import { JournalView } from './features/journal/JournalView';
import { DashboardView } from './features/journey/DashboardView';
import { Onboarding } from './features/onboarding/Onboarding';
import { GuidePage } from './features/public/PublicPages';
import { SettingsView } from './features/settings/SettingsView';
import { StaffDashboard } from './features/staff/StaffDashboard';
import './style.css';
import './themes.css';
import './path.css';
import './path-app.css';
import './path-screens.css';
import './features/journey/journey.css';
import './features/app/auth.css';
import './features/onboarding/onboarding.css';
import './features/settings/settings.css';
import './fonts.css';

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => navigator.serviceWorker.register('/sw.js'));
}

const refreshDemo = async () => undefined;
const updatePlanDemo = async () => undefined;

export function Root() {
  const currentLocation = useLocation();
  const query = new URLSearchParams(currentLocation.search);
  if (query.has('admin')) return <Navigate to="/staff" replace />;
  if (query.has('feedback')) return <Navigate to="/feedback" replace />;
  if (query.has('designs')) return import.meta.env.DEV ? <Navigate to="/dev/designs" replace /> : <Navigate to="/" replace />;
  return <Routes>
    <Route path="/" element={<App />} />
    <Route path="/app/*" element={<App />} />
    <Route path="/journal" element={<App initialScreen="journal" />} />
    <Route path="/settings" element={<App initialScreen="settings" />} />
    <Route path="/feedback" element={<FeedbackView />} />
    <Route path="/staff" element={<StaffDashboard />} />
    <Route path="/guide/craving" element={<GuidePage guide="craving" />} />
    <Route path="/guide/coffee" element={<GuidePage guide="coffee" />} />
    <Route path="/guide/recovery" element={<GuidePage guide="recovery" />} />
    {import.meta.env.DEV && <Route path="/dev/designs" element={<PathShowcase />} />}
    {import.meta.env.DEV && <Route path="/dev/onboarding" element={<Onboarding onDone={() => undefined} />} />}
    {import.meta.env.DEV && <Route path="/dev/dashboard" element={<DashboardView dashboard={journeyDashboardDemo} refresh={refreshDemo} updatePlan={updatePlanDemo} />} />}
    {import.meta.env.DEV && <Route path="/dev/dashboard/paused" element={<DashboardView dashboard={journeyPausedDemo} refresh={refreshDemo} updatePlan={updatePlanDemo} />} />}
    {import.meta.env.DEV && <Route path="/dev/dashboard/preparation" element={<DashboardView dashboard={journeyPreparationDemo} refresh={refreshDemo} updatePlan={updatePlanDemo} />} />}
    {import.meta.env.DEV && <Route path="/dev/dashboard/last-pack" element={<DashboardView dashboard={journeyLastPackDemo} refresh={refreshDemo} updatePlan={updatePlanDemo} />} />}
    {import.meta.env.DEV && <Route path="/dev/dashboard/recovery" element={<DashboardView dashboard={journeyRecoveryDemo} refresh={refreshDemo} updatePlan={updatePlanDemo} />} />}
    {import.meta.env.DEV && <Route path="/dev/coping" element={<CopingFlow open demo reason="Хочу просыпаться легче." initialTechniques={copingTechniquesDemo} onClose={() => undefined} onCompleted={() => undefined} />} />}
    {import.meta.env.DEV && <Route path="/dev/journal" element={<JournalView onBack={() => undefined} onSupport={() => undefined} loadJournal={journalDemo} updateEvent={journalUpdateDemo} />} />}
    {import.meta.env.DEV && <Route path="/dev/settings" element={<SettingsView onBack={() => undefined} />} />}
    <Route path="*" element={<Navigate to="/" replace />} />
  </Routes>;
}

const container = document.getElementById('root')!;
const hotWindow = window as typeof window & { __kurilkaRoot?: ReturnType<typeof createRoot> };
const appRoot = hotWindow.__kurilkaRoot ??= createRoot(container);
appRoot.render(<BrowserRouter><Root /></BrowserRouter>);
