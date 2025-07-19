import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { HomePage } from './pages/HomePage';
import { EditorPage } from './pages/EditorPage';
import { Header } from './components/Header';

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-secondary-50">
        <Header />
        <main className="container mx-auto px-4 py-8">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/editor/:sessionId" element={<EditorPage />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;