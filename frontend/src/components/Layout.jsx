import React, { useState } from 'react';
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import PipelineProgressBar from './PipelineProgressBar';

const Layout = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout, isAuthenticated } = useAuth();
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const isHome = location.pathname === '/';

  return (
    <div className="layout min-h-screen flex flex-col bg-slate-50">
      <header className="site-header bg-slate-900 text-white shadow-lg sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 flex items-center justify-between h-16">
          <Link to="/" className="flex items-center gap-3 font-heading text-xl font-semibold tracking-tight text-white hover:text-amber-200 transition-colors">
            <img src="/Plan_Analytics.png" alt="" className="h-9 w-auto object-contain rounded-xl" aria-hidden />
            <span>NEC Engineering Analysis</span>
          </Link>
          <nav className="flex items-center gap-4 sm:gap-6" aria-label="Main navigation">
            <Link
              to="/"
              className={`text-sm font-medium transition-colors ${
                isHome ? 'text-amber-400' : 'text-slate-300 hover:text-white'
              }`}
            >
              Home
            </Link>
            {isAuthenticated ? (
              <>
                <Link
                  to="/dashboard"
                  className={`text-sm font-medium transition-colors ${
                    location.pathname === '/dashboard' ? 'text-amber-400' : 'text-slate-300 hover:text-white'
                  }`}
                >
                  Dashboard
                </Link>
                <Link
                  to="/analysis"
                  className={`text-sm font-medium transition-colors ${
                    location.pathname.startsWith('/analysis') || location.pathname.startsWith('/programme') || location.pathname.startsWith('/review') || location.pathname.startsWith('/results')
                      ? 'text-amber-400'
                      : 'text-slate-300 hover:text-white'
                  }`}
                >
                  Analysis
                </Link>
                <Link
                  to="/help"
                  className={`text-sm font-medium transition-colors ${
                    location.pathname === '/help' ? 'text-amber-400' : 'text-slate-300 hover:text-white'
                  }`}
                >
                  Help
                </Link>
                <div className="relative">
                  <button
                    type="button"
                    onClick={() => setUserMenuOpen((o) => !o)}
                    className="flex items-center gap-2 text-sm font-medium text-slate-300 hover:text-white"
                    aria-expanded={userMenuOpen}
                    aria-haspopup="true"
                  >
                    {user?.name || user?.email || 'Account'}
                    <span className="text-xs">▼</span>
                  </button>
                  {userMenuOpen && (
                    <>
                      <div
                        className="fixed inset-0 z-40"
                        aria-hidden
                        onClick={() => setUserMenuOpen(false)}
                      />
                      <div className="absolute right-0 mt-1 w-48 py-1 bg-white rounded-lg shadow-lg border border-slate-200 z-50">
                        <Link
                          to="/account"
                          className="block px-4 py-2 text-sm text-slate-800 hover:bg-slate-100"
                          onClick={() => setUserMenuOpen(false)}
                        >
                          Account settings
                        </Link>
                        <button
                          type="button"
                          className="block w-full text-left px-4 py-2 text-sm text-slate-800 hover:bg-slate-100"
                          onClick={() => {
                            setUserMenuOpen(false);
                            logout();
                            navigate('/');
                          }}
                        >
                          Sign out
                        </button>
                      </div>
                    </>
                  )}
                </div>
              </>
            ) : (
              <>
                <Link
                  to="/help"
                  className={`text-sm font-medium transition-colors ${
                    location.pathname === '/help' ? 'text-amber-400' : 'text-slate-300 hover:text-white'
                  }`}
                >
                  Help
                </Link>
                <Link
                  to="/login"
                  className="text-sm font-medium text-slate-300 hover:text-white"
                >
                  Sign in
                </Link>
                <Link
                  to="/signup"
                  className="inline-flex items-center px-4 py-2 rounded-lg bg-amber-500 text-slate-900 text-sm font-semibold hover:bg-amber-400 transition-all duration-300 hover:scale-105"
                >
                  Get started
                </Link>
              </>
            )}
          </nav>
        </div>
      </header>

      <main className="flex-1">
        <PipelineProgressBar />
        <Outlet />
      </main>

      <footer className="site-footer bg-slate-800 text-slate-400 py-10 mt-auto">
        <div className="max-w-6xl mx-auto px-4 sm:px-6">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-2 font-heading font-semibold text-white">
              <img src="/Plan_Analytics.png" alt="" className="h-8 w-auto object-contain opacity-90 rounded-lg" aria-hidden />
              NEC Engineering Analysis
            </div>
            <p className="text-sm">
              Analyse your NEC contract, compare it to the programme, and get an aligned validation summary.
            </p>
          </div>
          <div className="mt-6 pt-6 border-t border-slate-700 text-center text-sm text-slate-500">
            © {new Date().getFullYear()} NEC Engineering Analysis System. All rights reserved.
          </div>
        </div>
      </footer>
    </div>
  );
};

export default Layout;
