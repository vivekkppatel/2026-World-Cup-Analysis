import Dashboard from './components/Dashboard.jsx'

/**
 * App — the dashboard opens directly (the kick-off mini-game was removed).
 * If you ever want a landing/intro screen back, gate <Dashboard/> behind a
 * `useState` phase flag here.
 */
export default function App() {
  return <Dashboard />
}
