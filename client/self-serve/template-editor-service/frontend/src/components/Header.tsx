import { Link } from 'react-router-dom';

export const Header: React.FC = () => {
  return (
    <header className="navbar-glass">
      <div className="container mx-auto px-6">
        <div className="flex items-center justify-between h-20">
          <Link to="/" className="flex items-center space-x-4">
            <img 
              src="/ceneca-light.png" 
              alt="Ceneca" 
              className="w-20 h-20"
            />
            <div className="flex items-center">
              <span className="text-3xl font-bold gradient-text font-baskerville">
                Ceneca
              </span>
            </div>
          </Link>
          
          <nav className="flex items-center">
            <Link
              to="/"
              className="text-lg font-medium text-foreground hover:text-primary transition-colors font-baskerville px-4 py-2"
            >
              Home
            </Link>
          </nav>
        </div>
      </div>
    </header>
  );
};