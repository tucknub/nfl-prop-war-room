import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './App.jsx';
import fixtureWeek from '../fixtures/data/2026/week-02.test.json';
import manifest from '../public/data/manifest.json';
import './styles.css';

const fixtureEntry = {
  id: '2026-w2-fixture', season: 2026, week: 2, label: '2026 · Week 2 · TEST FIXTURE', updated: 'Test fixture', fixture: true,
  gameDates: { 'AAA @ BBB': '2026-09-20T13:00:00-04:00', 'CCC @ DDD': '2026-09-20T16:25:00-04:00' },
};
const entries = [...manifest.productionWeeks, fixtureEntry];
const loader = async (entry) => {
  if (entry.fixture) return fixtureWeek;
  const response = await fetch(new URL(entry.path, document.baseURI));
  if (!response.ok) throw new Error(`Week package failed to load (${response.status})`);
  return response.json();
};

createRoot(document.getElementById('root')).render(<StrictMode><App weekEntries={entries} loader={loader} /></StrictMode>);
