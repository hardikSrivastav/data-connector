import React from 'react';
import { Link } from 'react-router-dom';
import { FileText, Settings } from 'lucide-react';

export const Header: React.FC = () => {
  return (
    <header className="bg-white shadow-sm border-b border-secondary-200">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          <Link to="/" className="flex items-center space-x-2">
            <FileText className="w-8 h-8 text-primary-600" />
            <span className="text-xl font-bold text-secondary-900">
              Template Editor
            </span>
          </Link>
          
          <nav className="flex items-center space-x-4">
            <Link
              to="/"
              className="text-secondary-600 hover:text-secondary-900 transition-colors"
            >
              Home
            </Link>
            <button className="p-2 text-secondary-600 hover:text-secondary-900 transition-colors">
              <Settings className="w-5 h-5" />
            </button>
          </nav>
        </div>
      </div>
    </header>
  );
};