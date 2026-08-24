import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { beforeEach, describe, expect, it } from 'vitest'

import { CONFIG, configWith, server } from '@test'
import type { ConfigResponse } from '../../../api/generated/types.gen.ts'
import { probeOllama } from '../../../libs/probeOllama/probeOllama.ts'
import { ProviderSettings } from './ProviderSettings.tsx'

/** The `llm` section a case wants, over the configured Anthropic default. */
type Llm = ConfigResponse['sections']['llm']

/**
 * The component under test, with the provider overridden per case.
 *
 * Inside a router: the Ollama branch probes its endpoint through a fetcher,
 * so the resource route has to exist even for the cases that never show it.
 */
function renderWith(llm?: Llm, rest: Partial<ConfigResponse> = {}) {
  const config = llm ? configWith({ llm }, rest) : { ...CONFIG, ...rest }
  const router = createMemoryRouter([
    { path: '/', Component: () => <ProviderSettings config={config} /> },
    { path: '/settings/ollama', loader: probeOllama },
  ])
  return render(<RouterProvider router={router} />)
}

/** A hosted provider, which is the shape the cloud branch draws. */
function cloud(provider: 'anthropic' | 'openai' | 'gemini'): Llm {
  return {
    provider,
    model_analysis: 'claude-opus',
    model_generation: 'claude-haiku',
    context_window: 200000,
  }
}

/** A local one, which is the only shape carrying an endpoint. */
function local(provider: 'ollama' | 'custom'): Llm {
  return {
    provider,
    endpoint_url: 'http://localhost:11434',
    model_analysis: 'qwen3:8b',
    model_generation: 'qwen3:8b',
    context_window: 32768,
  }
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
    renderWith(undefined, { llm_configured: configured })

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
      (provider) => {
        renderWith(cloud(provider as 'anthropic' | 'openai' | 'gemini'))

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
      renderWith(local('ollama'))

      expect(
        screen.getByRole('textbox', { name: 'Ollama URL' }),
      ).toBeInTheDocument()
      expect(screen.queryByLabelText('API Key')).not.toBeInTheDocument()
    })

    it('shows the custom fields, key included, since some servers want one', () => {
      renderWith(local('custom'))

      expect(
        screen.getByRole('textbox', { name: 'API Base URL' }),
      ).toBeInTheDocument()
      expect(screen.getByLabelText(/API Key/)).toBeInTheDocument()
    })
  })

  describe('choosing a different provider', () => {
    it('swaps the fields under it before anything is saved', async () => {
      const user = userEvent.setup()
      renderWith(cloud('anthropic'))

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
      renderWith(undefined, { from_env: ['llm.provider'] })

      const select = screen.getByRole('combobox', { name: 'Provider' })
      expect(select).toBeDisabled()
      expect(select).toHaveAccessibleDescription(
        'Set by MEDIASAGE_LLM__PROVIDER. Edit .env to change it.',
      )
    })

    it('still submits it, since a disabled control is left out', () => {
      // Without it the save cannot tell a custom provider from any other.
      renderWith(local('custom'), { from_env: ['llm.provider'] })

      expect(screen.getByDisplayValue('custom')).toHaveAttribute(
        'name',
        'llm.provider',
      )
    })
  })
})
