import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const HomePage = () => {
  const { isAuthenticated } = useAuth();
  const steps = [
    {
      step: '1',
      title: 'Analyze the contract',
      description: 'Upload your NEC contract (PDF or DOCX). We extract scope items, admin items, key dates, constraints, and drawing references.',
      icon: (
        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
      ),
    },
    {
      step: '2',
      title: 'Compare to the programme',
      description: 'Submit your programme (e.g. .xer). We compare it to the contract: dates, required activities, scope evidence, and constraint coverage.',
      icon: (
        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
        </svg>
      ),
    },
    {
      step: '3',
      title: 'Aligned summary',
      description: 'Get a Programme Validation Report: executive summary, programme decision, scope evidence table, required activities, and clear next steps.',
      icon: (
        <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
    },
  ];

  return (
    <div className="home-page">
      {/* Hero */}
      <section className="hero bg-slate-900 text-white py-20 sm:py-28 overflow-hidden relative">
        <div className="hero-glow absolute inset-0 opacity-30 pointer-events-none" aria-hidden />
        <div className="max-w-6xl mx-auto px-4 sm:px-6 text-center relative">
          <h1 className="hero-title font-heading text-4xl sm:text-5xl md:text-6xl font-bold tracking-tight text-white max-w-4xl mx-auto leading-tight">
            Contract, programme, aligned
          </h1>
          <p className="hero-subtitle mt-6 text-lg sm:text-xl text-slate-300 max-w-2xl mx-auto">
            Analyze your NEC contract, compare it to the programme, and get a clear validation summary—scope evidence, required activities, and next steps in one place.
          </p>
          <div className="hero-buttons mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link
              to={isAuthenticated ? '/analysis' : '/signup'}
              className="btn-primary inline-flex items-center justify-center px-8 py-4 rounded-xl bg-amber-500 text-slate-900 font-semibold text-lg hover:bg-amber-400 transition-all duration-300 hover:scale-105 hover:shadow-xl hover:shadow-amber-500/30"
            >
              {isAuthenticated ? 'Start analysis' : 'Get started'}
            </Link>
            <a
              href="#how-it-works"
              className="btn-secondary inline-flex items-center justify-center px-8 py-4 rounded-xl border-2 border-slate-600 text-slate-200 font-semibold text-lg hover:border-slate-500 hover:bg-slate-800/50 transition-all duration-300 hover:scale-[1.02]"
            >
              How it works
            </a>
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="how-it-works" className="py-16 sm:py-24 bg-white">
        <div className="max-w-6xl mx-auto px-4 sm:px-6">
          <h2 className="section-title font-heading text-3xl sm:text-4xl font-bold text-slate-900 text-center mb-4">
            How it works
          </h2>
          <p className="section-subtitle text-slate-600 text-center max-w-2xl mx-auto mb-14">
            Three steps: analyze the contract, compare it to the programme, then get an aligned validation summary with clear actions.
          </p>
          <div className="grid sm:grid-cols-3 gap-8 sm:gap-10">
            {steps.map((item, index) => (
              <div
                key={index}
                className="feature-card p-6 rounded-2xl bg-slate-50 border border-slate-200/80 hover:border-amber-300/50 hover:shadow-lg hover:shadow-amber-500/10 transition-all duration-300 hover:-translate-y-1"
                style={{ animationDelay: `${200 + index * 120}ms` }}
              >
                <div className="flex items-center gap-3 mb-4">
                  <span className="step-badge flex h-10 w-10 items-center justify-center rounded-full bg-amber-500 text-slate-900 font-heading font-bold text-lg">
                    {item.step}
                  </span>
                  <div className="w-12 h-12 rounded-xl bg-amber-500/10 text-amber-600 flex items-center justify-center shrink-0">
                    {item.icon}
                  </div>
                </div>
                <h3 className="font-heading text-xl font-semibold text-slate-900 mb-2">
                  {item.title}
                </h3>
                <p className="text-slate-600 text-sm leading-relaxed">
                  {item.description}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="cta-section py-16 sm:py-24 bg-slate-100">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 text-center">
          <h2 className="cta-title font-heading text-3xl sm:text-4xl font-bold text-slate-900 mb-4">
            Ready to get started?
          </h2>
          <p className="text-slate-600 max-w-xl mx-auto mb-8">
            Upload your contract to analyze scope, then add your programme to compare and get your aligned validation summary.
          </p>
          <Link
            to={isAuthenticated ? '/analysis' : '/signup'}
            className="btn-primary inline-flex items-center justify-center px-8 py-4 rounded-xl bg-amber-500 text-slate-900 font-semibold text-lg hover:bg-amber-400 transition-all duration-300 hover:scale-105 hover:shadow-xl hover:shadow-amber-500/30"
          >
            {isAuthenticated ? 'Analyse contract' : 'Get started'}
          </Link>
        </div>
      </section>
    </div>
  );
};

export default HomePage;
