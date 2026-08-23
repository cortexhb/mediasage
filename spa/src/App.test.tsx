import { render, screen } from '@testing-library/react'
import { http, HttpResponse } from 'msw'
import { describe, expect, it } from 'vitest'

import App from './App.tsx'
import { server } from '@test'

describe('App', () => {
  it('reports the API payload once it answers', async () => {
    server.use(
      http.get('/api/health', () => HttpResponse.json({ status: 'healthy' })),
    )

    render(<App />)

    expect(await screen.findByText(/healthy/)).toBeInTheDocument()
  })

  it('shows the status code when the API answers with a failure', async () => {
    server.use(
      http.get('/api/health', () => new HttpResponse(null, { status: 503 })),
    )

    render(<App />)

    expect(await screen.findByText(/returned 503/)).toBeInTheDocument()
  })

  it('reports the API as unreachable when the request cannot complete', async () => {
    server.use(http.get('/api/health', () => HttpResponse.error()))

    render(<App />)

    expect(await screen.findByText(/API unreachable/)).toBeInTheDocument()
  })

  it('shows a pending message before the API answers', () => {
    server.use(
      http.get('/api/health', () => HttpResponse.json({ status: 'healthy' })),
    )

    render(<App />)

    expect(screen.getByText(/Reaching the API/)).toBeInTheDocument()
  })
})
