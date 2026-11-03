import React, { useState, useEffect, useCallback } from 'react';
import {
  BundleData,
  StatusData,
  AuditSeriesData,
  GatesData,
  PipelineData,
  ConceptCheckData,
  FeedData,
  ConsensusItem,
  BetasData,
} from './types/macro';
import {
  DEFAULT_BUNDLE,
  DEFAULT_STATUS,
  DEFAULT_AUDIT,
  DEFAULT_GATES,
  DEFAULT_PIPELINE,
  DEFAULT_CONCEPT_CHECK,
} from './data/defaultData';
import { DeskView } from './components/DeskView';
import { LanjutanView } from './components/LanjutanView';
import { MacroSearchModal } from './components/MacroSearchModal';

const dataUrl = (file: string) => new URL(`data/${file}`, document.baseURI).toString();

export const App: React.FC = () => {
  const [currentView, setCurrentView] = useState<'desk' | 'lanjutan'>('desk');
  const [isMacroSearchOpen, setIsMacroSearchOpen] = useState(false);
  const [bundle, setBundle] = useState<BundleData>(DEFAULT_BUNDLE);
  const [status, setStatus] = useState<StatusData>(DEFAULT_STATUS);
  const [audit, setAudit] = useState<AuditSeriesData>(DEFAULT_AUDIT);
  const [gates, setGates] = useState<GatesData>(DEFAULT_GATES);
  const [pipeline, setPipeline] = useState<PipelineData>(DEFAULT_PIPELINE);
  const [conceptCheck, setConceptCheck] = useState<ConceptCheckData>(DEFAULT_CONCEPT_CHECK);
  const [feed, setFeed] = useState<FeedData | null>(null);
  const [consensus, setConsensus] = useState<ConsensusItem[]>([]);
  const [betas, setBetas] = useState<BetasData | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [clock, setClock] = useState('');
  const [theme, setTheme] = useState<'light' | 'dark'>('dark');

  useEffect(() => {
    const updateTime = () => setClock(`${new Date().toISOString().slice(11, 19)} UTC`);
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  const loadData = useCallback(async () => {
    setIsRefreshing(true);
    const now = Date.now();

    const loadJson = async <T,>(file: string): Promise<T | null> => {
      try {
        const response = await fetch(`${dataUrl(file)}?t=${now}`, { cache: 'no-store' });
        if (!response.ok) return null;
        return (await response.json()) as T;
      } catch {
        return null;
      }
    };

    try {
      const [bundleData, statusData, auditData, gatesData, pipelineData, conceptData, feedData, betasData] =
        await Promise.all([
          loadJson<BundleData>('bundle.json'),
          loadJson<StatusData>('status.json'),
          loadJson<AuditSeriesData>('audit_series.json'),
          loadJson<GatesData>('gates.json'),
          loadJson<PipelineData>('pipeline.json'),
          loadJson<ConceptCheckData>('concept_check.json'),
          loadJson<FeedData>('feed.json'),
          loadJson<BetasData>('betas.json'),
        ]);

      if (bundleData?.series && Object.keys(bundleData.series).length) setBundle(bundleData);
      if (statusData?.counts) setStatus(statusData);
      if (auditData?.checks) setAudit(auditData);
      if (gatesData?.umum) setGates(gatesData);
      if (pipelineData?.steps) setPipeline(pipelineData);
      if (conceptData?.violations) setConceptCheck(conceptData);
      if (feedData?.generated) setFeed(feedData);
      if (betasData?.assets) setBetas(betasData);

      try {
        const response = await fetch(`${dataUrl('consensus.csv')}?t=${now}`, { cache: 'no-store' });
        if (response.ok) {
          const text = await response.text();
          const items: ConsensusItem[] = text
            .split('\n')
            .map((line) => line.split(',').map((x) => x.trim()))
            .filter((parts) => /^20\d\d-\d\d-\d\d$/.test(parts[0]) && parts.length >= 3)
            .map((parts) => ({
              date: parts[0],
              ind: parts[1],
              cons: parseFloat(parts[2]),
            }))
            .filter((item) => !isNaN(item.cons));
          if (items.length) setConsensus(items);
        }
      } catch {
        // ignore
      }
    } finally {
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
    const interval = setInterval(() => void loadData(), 10 * 60 * 1000);
    return () => clearInterval(interval);
  }, [loadData]);

  const goTo = (view: 'desk' | 'lanjutan') => {
    setCurrentView(view);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
      <header className="top">
        <div className="wrap">
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div className="terminal-brand"><span className="terminal-logo-box">QT</span><span>MACRO ENGINE // QUANT DESK</span></div>
            <span className="ping-indicator"><span className="ping-dot" />LIVE · {clock}</span>
          </div>

          <nav aria-label="Navigasi Terminal">
            {currentView === 'desk' ? (
              <>
                <a href="#pasar" className="active">Pasar</a>
                <a href="#aliran">Aliran Modal</a>
                <a href="#makro">Makro</a>
                <a href="#kebijakan">Kebijakan</a>
                <a href="#stres">Stres & Likuiditas</a>
                <a href="#posisi">COT</a>
                <a href="#kalender">Kalender</a>
                <a href="#data">Kesehatan</a>
                <button type="button" onClick={() => goTo('lanjutan')}>Workbench Sinyal →</button>
              </>
            ) : (
              <>
                <button type="button" onClick={() => goTo('desk')}>← Beranda Terminal</button>
                <span className="small mute">[MODULE: QUANTITATIVE WORKBENCH & SIGNAL MODEL]</span>
              </>
            )}
          </nav>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span className=\"terminal-time\">{clock}</span>
            <button type=\"button\" className=\"btn sm\" onClick={() => setIsMacroSearchOpen(true)}>⚡ INTEL SEARCH</button>
            <button type=\"button\" className=\"btn sm\" onClick={() => void loadData()} disabled={isRefreshing}>{isRefreshing ? 'SYNCING…' : 'SYNC'}</button>
            <button type=\"button\" className=\"btn sm\" onClick={() => setTheme((value) => value === 'dark' ? 'light' : 'dark')} aria-label=\"Toggle theme\">{theme === 'dark' ? '☀' : '🌙'}</button>
          </div>
        </div>
      </header>

      <div style={{ flex: 1 }}>
        {currentView === 'desk' ? (
          <DeskView
            bundle={bundle}
            status={status}
            audit={audit}
            gates={gates}
            pipeline={pipeline}
            conceptCheck={conceptCheck}
            feed={feed}
            consensus={consensus}
            onNavigateToLanjutan={() => goTo('lanjutan')}
          />
        ) : (
          <LanjutanView
            betasData={betas}
            onBackToDesk={() => goTo('desk')}
          />
        )}
      </div>

      <MacroSearchModal
        isOpen={isMacroSearchOpen}
        onClose={() => setIsMacroSearchOpen(false)}
      />
    </div>
  );
};
