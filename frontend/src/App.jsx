import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { useAuth } from './auth/AuthContext';
import AppShell from './components/AppShell';
import LoginPage from './pages/LoginPage';
import ComingSoon from './pages/ComingSoon';
import DashboardPage from './pages/DashboardPage';
import ProjectsPage from './pages/ProjectsPage';
import ProjectDetailPage from './pages/ProjectDetailPage';

function RequireAuth({ children, roles }) {
  const { user } = useAuth();
  const location = useLocation();
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (roles && !roles.includes(user.role)) return <Navigate to="/" replace />;
  return children;
}

const only = (roles, element) => <RequireAuth roles={roles}>{element}</RequireAuth>;

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<RequireAuth><AppShell /></RequireAuth>}>
        <Route index element={<DashboardPage />} />
        <Route path="my-work" element={only(['employee'], <ComingSoon title="My work" />)} />
        <Route path="projects" element={<ProjectsPage />} />
        <Route path="projects/:projectId" element={<ProjectDetailPage />} />
        <Route path="actions" element={<ComingSoon title="Action Center" />} />
        <Route path="workload" element={only(['admin', 'manager'], <ComingSoon title="Workload" />)} />
        <Route path="people" element={only(['admin', 'manager'], <ComingSoon title="People" />)} />
        <Route path="archive" element={only(['admin'], <ComingSoon title="Archive" />)} />
        <Route path="audit" element={only(['admin'], <ComingSoon title="Audit log" />)} />
        <Route path="profile" element={<ComingSoon title="Your profile" />} />
        <Route path="*" element={<ComingSoon title="Page not found" message="That page doesn't exist. Use the menu to find what you need." />} />
      </Route>
    </Routes>
  );
}