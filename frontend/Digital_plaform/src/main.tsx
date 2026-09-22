import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { ArchitectureFlow } from './components/ArchitectureFlow.tsx'

const isArchitectureRoute = window.location.pathname === '/architecture' || new URLSearchParams(window.location.search).get('view') === 'flow'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    {isArchitectureRoute ? <ArchitectureFlow /> : <App />}
  </StrictMode>,
)
