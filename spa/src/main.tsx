import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router'

import { routes } from './routes.ts'
import './style.css'

const container = document.getElementById('root')
// Thrown rather than asserted away: a missing root is a broken index.html,
// and a silent no-op would look like a blank page for no stated reason.
if (!container) {
  throw new Error('index.html is missing its #root element')
}

// Built once, outside the React tree: a data router held in React state is
// recreated on every render and loses its navigation history.
const router = createBrowserRouter(routes)

createRoot(container).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
)
