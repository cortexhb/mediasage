import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { beforeEach, describe, expect, it } from 'vitest'

import { server } from '@test'
import type { ConfigResponse } from '../../../api/generated/types.gen.ts'
import { probeOllama } from '../../../libs/probeOllama/probeOllama.ts'
import { ProviderSettings } from './ProviderSettings.tsx'

/** A configured Anthropic deployment, which is the common case. */
const CONFIG: ConfigResponse = {
  version: '1.0.0',
  plex_connected: true,
  plex_linked: true,
  plex_server_name: 'Living Room',
  plex_server_id: 'abc123',
  music_library: 'Music',
  llm_provider: 'anthropic',
  llm_configured: true,
  llm_api_key_set: true,
  model_analysis: 'claude-opus',
  model_generation: 'claude-haiku',
  max_tracks_to_ai: 500,
  max_albums_to_ai: 100,
  defaults: { track_count: 25 },
  context_window: 200000,
}

/**
 * The component under test, with the provider overridden per case.
 *
 * Inside a router: the Ollama branch probes its endpoint through a fetcher,
 * so the resource route has to exist even for the cases that never show it.
 */
function renderWith(config: Partial<ConfigResponse> = {}) {
  const router = createMemoryRouter([
    {
      path: '/',
      Component: () => <ProviderSettings config={{ ...CONFIG, ...config }} />,
    },
    { path: '/settings/ollama', loader: probeOllama },
  ])
  return render(<RouterProvider router={router} />)
}

describe('ProviderSettings', () => {
  beforeEach(() => {
    // A local server that answers, for the branches that reach one.
    server.use(
      http.get('/api/ollama/status', () =>
        HttpResponse.json({ connected: true, model_count: 1 }),
      ),
      http.get('/api/ollama/models', () =>
        HttpResponse.json({ models: [{ name: 'qwen3:8b' }] }),
      ),
      http.get('/api/ollama/model-info', () =>
        HttpResponse.json({ name: 'qwen3:8b', context_window: 32768 }),
      ),
    )
  })

  it.each([
    [true, 'Configured'],
    [false, 'Not configured'],
  ])('reports llm_configured=%s as "%s"', (configured, reported) => {
    renderWith({ llm_configured: configured })

    expect(screen.getByRole('status')).toHaveTextContent(reported)
  })

  it('offers every provider the backend accepts', () => {
    renderWith()

    const select = screen.getByRole('combobox', { name: 'Provider' })
    expect(select).toHaveValue('anthropic')
    for (const label of [
      'Anthropic (Claude)',
      'OpenAI (GPT)',
      'Google (Gemini)',
      'Ollama (Local)',
      'Custom (OpenAI-compatible)',
    ]) {
      expect(screen.getByRole('option', { name: label })).toBeInTheDocument()
    }
  })

  describe('a cloud provider', () => {
    it.each(['anthropic', 'openai', 'gemini'])(
      'asks %s for a key and nothing else',
      (llm_provider) => {
        renderWith({ llm_provider })

        expect(screen.getByLabelText('API Key')).toBeInTheDocument()
        expect(
          screen.queryByRole('textbox', { name: 'Ollama URL' }),
        ).not.toBeInTheDocument()
        expect(
          screen.queryByRole('textbox', { name: 'API Base URL' }),
        ).not.toBeInTheDocument()
      },
    )

    it('says that leaving the key blank keeps the stored one', () => {
      renderWith()

      expect(screen.getByLabelText('API Key')).toHaveAccessibleDescription(
        'Leave blank to keep the stored key.',
      )
    })
  })

  describe('a local provider', () => {
    it('shows the Ollama fields and no API key', () => {
      renderWith({ llm_provider: 'ollama' })

      expect(
        screen.getByRole('textbox', { name: 'Ollama URL' }),
      ).toBeInTheDocument()
      expect(screen.queryByLabelText('API Key')).not.toBeInTheDocument()
    })

    it('shows the custom fields, key included, since some servers want one', () => {
      renderWith({ llm_provider: 'custom' })

      expect(
        screen.getByRole('textbox', { name: 'API Base URL' }),
      ).toBeInTheDocument()
      expect(screen.getByLabelText(/API Key/)).toBeInTheDocument()
    })
  })

  describe('choosing a different provider', () => {
    it('swaps the fields under it before anything is saved', async () => {
      const user = userEvent.setup()
      renderWith({ llm_provider: 'anthropic' })

      await user.selectOptions(
        screen.getByRole('combobox', { name: 'Provider' }),
        'ollama',
      )

      expect(
        screen.getByRole('textbox', { name: 'Ollama URL' }),
      ).toBeInTheDocument()
      expect(screen.queryByLabelText('API Key')).not.toBeInTheDocument()
    })
  })

  describe('when the deployment sets the provider', () => {
    it('refuses the change and says where it comes from', () => {
      renderWith({ provider_from_env: true })

      const select = screen.getByRole('combobox', { name: 'Provider' })
      expect(select).toBeDisabled()
      expect(select).toHaveAccessibleDescription(
        'Set by LLM_PROVIDER. Edit .env to change it.',
      )
    })

    it('still submits it, since a disabled control is left out', () => {
      // Without it the save cannot tell a custom provider from any other.
      renderWith({ provider_from_env: true, llm_provider: 'custom' })

      expect(screen.getByDisplayValue('custom')).toHaveAttribute(
        'name',
        'llm_provider',
      )
    })
  })
})
