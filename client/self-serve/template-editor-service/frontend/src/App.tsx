import { BrowserRouter as Router, Routes, Route, useLocation } from 'react-router-dom';
import { HomePage } from './pages/HomePage';
import { EditorPage } from './pages/EditorPage';

function AppContent() {
  const location = useLocation();
  const isEditorPage = location.pathname.startsWith('/editor/');
  
  // Check for direct session access via URL params (integration mode)
  const urlParams = new URLSearchParams(location.search);
  const sessionId = urlParams.get('session_id');
  const isIntegration = urlParams.get('integration') === 'true';
  
  // If we have session_id in URL params, redirect to editor
  if (sessionId && !isEditorPage) {
    window.location.href = `/editor/${sessionId}${isIntegration ? '?integration=true' : ''}`;
    return <div>Redirecting to editor...</div>;
  }

  if (isEditorPage) {
    return (
      <div className="h-screen bg-background text-foreground">
        <Routes>
          <Route path="/editor/:sessionId" element={<EditorPage />} />
        </Routes>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <main className="container mx-auto px-6 py-12">
        <Routes>
          <Route path="/" element={<HomePage />} />
        </Routes>
      </main>
    </div>
  );
}

function App() {
  return (
    <Router>
      <AppContent />
    </Router>
  );
}

export default App;