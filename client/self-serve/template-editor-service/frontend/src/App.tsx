import { BrowserRouter as Router, Routes, Route, useLocation } from 'react-router-dom';
import { HomePage } from './pages/HomePage';
import { EditorPage } from './pages/EditorPage';
import { Header } from './components/Header';

function AppContent() {
  const location = useLocation();
  const isEditorPage = location.pathname.startsWith('/editor/');

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
      <Header />
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