import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, it } from 'vitest'

import { server } from '@test'
import { probeOllama } from '../../../libs/probeOllama/probeOllama.ts'
import { OllamaSettings } from './OllamaSettings.tsx'
import type { OllamaSettingsProps } from './OllamaSettings.tsx'

/** A saved Ollama configuration. */
const PROPS: OllamaSettingsProps = {
  endpoint: 'http://localhost:11434',
  analysis: 'qwen3:8b',
  generation: 'qwen3:8b',
  contextWindow: 32768,
}

/** The fields under the real probe route, which the fetchers load. */
function renderFields(props: Partial<OllamaSettingsProps> = {}) {
  const router = createMemoryRouter([
    { path: '/', Component: () => <OllamaSettings {...PROPS} {...props} /> },
    { path: '/settings/ollama', loader: probeOllama },
  ])
  return render(<RouterProvider router={router} />)
}

/** A server holding `models`, answering every probe the form makes. */
function ollama(models: string[], contextWindow = 32768) {
  server.use(
    http.get('/api/ollama/status', () =>
      HttpResponse.json({ connected: true, model_count: models.length }),
    ),
    http.get('/api/ollama/models', () =>
      HttpResponse.json({ models: models.map((name) => ({ name })) }),
    ),
    http.get('/api/ollama/model-info', ({ request }) =>
      HttpResponse.json({
        name: new URL(request.url).searchParams.get('model'),
        context_window: contextWindow,
      }),
    ),
  )
}

describe('OllamaSettings', () => {
  it('shows the saved endpoint', async () => {
    ollama(['qwen3:8b'])
    renderFields({ endpoint: 'http://ollama:11434' })

    expect(
      await screen.findByRole('textbox', { name: 'Ollama URL' }),
    ).toHaveValue('http://ollama:11434')
  })

  it('falls back to the address Ollama listens on by default', async () => {
    ollama(['qwen3:8b'])
    renderFields({ endpoint: undefined })

    expect(
      await screen.findByRole('textbox', { name: 'Ollama URL' }),
    ).toHaveValue('http://localhost:11434')
  })

  describe('probing the endpoint', () => {
    it('loads the models without waiting for a save', async () => {
      ollama(['qwen3:8b', 'llama3:70b'])
      renderFields()

      // One per select: the analysis model and the generation model.
      expect(
        await screen.findAllByRole('option', { name: 'llama3:70b' }),
      ).toHaveLength(2)
      expect(screen.getByRole('status')).toHaveTextContent(
        'Connected (2 models)',
      )
    })

    it('re-probes an address the user typed', async () => {
      const user = userEvent.setup()
      const asked: string[] = []
      server.use(
        http.get('/api/ollama/status', ({ request }) => {
          asked.push(new URL(request.url).searchParams.get('url') ?? '')
          return HttpResponse.json({ connected: true, model_count: 1 })
        }),
        http.get('/api/ollama/models', () =>
          HttpResponse.json({ models: [{ name: 'qwen3:8b' }] }),
        ),
        http.get('/api/ollama/model-info', () =>
          HttpResponse.json({ name: 'qwen3:8b', context_window: 8192 }),
        ),
      )
      renderFields()

      await screen.findAllByRole('option', { name: 'qwen3:8b' })
      await user.clear(screen.getByRole('textbox', { name: 'Ollama URL' }))
      await user.type(
        screen.getByRole('textbox', { name: 'Ollama URL' }),
        'http://box:11434',
      )

      await waitFor(() => {
        expect(asked).toContain('http://box:11434')
      })
    })

    it('probes once for a typed address, not once per keystroke', async () => {
      const user = userEvent.setup()
      let probes = 0
      server.use(
        http.get('/api/ollama/status', () => {
          probes += 1
          return HttpResponse.json({ connected: true, model_count: 1 })
        }),
        http.get('/api/ollama/models', () =>
          HttpResponse.json({ models: [{ name: 'qwen3:8b' }] }),
        ),
        http.get('/api/ollama/model-info', () =>
          HttpResponse.json({ name: 'qwen3:8b', context_window: 8192 }),
        ),
      )
      renderFields()
      // The status renders before any probe lands; an option cannot.
      await screen.findAllByRole('option', { name: 'qwen3:8b' })
      const before = probes

      await user.type(
        screen.getByRole('textbox', { name: 'Ollama URL' }),
        '/v1',
      )
      await waitFor(() => {
        expect(probes).toBe(before + 1)
      })
    })

    it('reports a server that refused, and keeps the form usable', async () => {
      server.use(
        http.get('/api/ollama/status', () =>
          HttpResponse.json({ connected: false, error: 'connection refused' }),
        ),
      )
      renderFields()

      // Waited on the text: the status renders "Checking…" before it answers.
      await waitFor(() => {
        expect(screen.getByRole('status')).toHaveTextContent(
          'connection refused',
        )
      })
      expect(screen.getByRole('status')).toHaveAttribute('data-state', 'error')
      expect(screen.getByRole('textbox', { name: 'Ollama URL' })).toBeEnabled()
    })

    it('calls a reachable server with nothing pulled an error', async () => {
      server.use(
        http.get('/api/ollama/status', () =>
          HttpResponse.json({ connected: true, model_count: 0 }),
        ),
      )
      renderFields()

      await waitFor(() => {
        expect(screen.getByRole('status')).toHaveTextContent(
          'No models installed',
        )
      })
    })

    it('disables the model selects while there is nothing to choose', async () => {
      server.use(
        http.get('/api/ollama/status', () =>
          HttpResponse.json({ connected: false, error: 'down' }),
        ),
      )
      renderFields()

      await waitFor(() => {
        expect(screen.getByRole('status')).toHaveTextContent('down')
      })
      expect(
        screen.getByRole('combobox', { name: 'Analysis Model' }),
      ).toBeDisabled()
      expect(
        screen.getByRole('combobox', { name: 'Generation Model' }),
      ).toBeDisabled()
    })
  })

  describe('the context window', () => {
    it('is read from the chosen model, not typed', async () => {
      ollama(['qwen3:8b'], 40960)
      renderFields()

      expect(
        await screen.findByText(
          /Context window: 40,960 tokens \(~717 tracks\)/,
        ),
      ).toBeVisible()
    })

    it('follows the model the user picks', async () => {
      const user = userEvent.setup()
      server.use(
        http.get('/api/ollama/status', () =>
          HttpResponse.json({ connected: true, model_count: 2 }),
        ),
        http.get('/api/ollama/models', () =>
          HttpResponse.json({
            models: [{ name: 'qwen3:8b' }, { name: 'llama3:70b' }],
          }),
        ),
        http.get('/api/ollama/model-info', ({ request }) => {
          const model = new URL(request.url).searchParams.get('model')
          return HttpResponse.json({
            name: model,
            context_window: model === 'llama3:70b' ? 128000 : 32768,
          })
        }),
      )
      renderFields()

      await screen.findAllByRole('option', { name: 'llama3:70b' })
      await user.selectOptions(
        screen.getByRole('combobox', { name: 'Analysis Model' }),
        'llama3:70b',
      )

      expect(
        await screen.findByText(/128,000 tokens \(~2,284 tracks\)/),
      ).toBeVisible()
    })

    it('is submitted, so the detected value is what gets saved', async () => {
      ollama(['qwen3:8b'], 40960)
      renderFields()

      await screen.findByText(/40,960 tokens/)
      // The hidden field carrying it: no label, so found by its value.
      expect(screen.getByDisplayValue('40960')).toHaveAttribute(
        'name',
        'context_window',
      )
    })

    it('keeps the saved figure when the server does not report one', async () => {
      server.use(
        http.get('/api/ollama/status', () =>
          HttpResponse.json({ connected: true, model_count: 1 }),
        ),
        http.get('/api/ollama/models', () =>
          HttpResponse.json({ models: [{ name: 'qwen3:8b' }] }),
        ),
        http.get('/api/ollama/model-info', () =>
          HttpResponse.json({ name: 'qwen3:8b', context_window: null }),
        ),
      )
      renderFields({ contextWindow: 32768 })

      expect(await screen.findByText(/32,768 tokens/)).toBeVisible()
    })

    it('marks an undetected figure as the default, not as a reading', async () => {
      server.use(
        http.get('/api/ollama/status', () =>
          HttpResponse.json({ connected: true, model_count: 1 }),
        ),
        http.get('/api/ollama/models', () =>
          HttpResponse.json({ models: [{ name: 'qwen3:8b' }] }),
        ),
        http.get('/api/ollama/model-info', () =>
          HttpResponse.json({ name: 'qwen3:8b', context_window: null }),
        ),
      )
      renderFields({ contextWindow: 32768 })

      expect(await screen.findByText(/\(default\)/)).toBeVisible()
    })

    it('is not submitted unless it was detected', async () => {
      // Saving an assumed window writes a guess over the real setting.
      server.use(
        http.get('/api/ollama/status', () =>
          HttpResponse.json({ connected: true, model_count: 1 }),
        ),
        http.get('/api/ollama/models', () =>
          HttpResponse.json({ models: [{ name: 'qwen3:8b' }] }),
        ),
        http.get('/api/ollama/model-info', () =>
          HttpResponse.json({ name: 'qwen3:8b', context_window: null }),
        ),
      )
      renderFields({ contextWindow: 32768 })

      await screen.findByText(/\(default\)/)
      expect(screen.queryByDisplayValue('32768')).not.toBeInTheDocument()
    })
  })

  describe('a server that lacks the saved models', () => {
    it('falls back to one it holds when neither survived', async () => {
      ollama(['llama3:70b'])
      renderFields({ analysis: 'qwen3:8b', generation: 'qwen3:8b' })

      await waitFor(() => {
        expect(
          screen.getByRole('combobox', { name: 'Analysis Model' }),
        ).toHaveValue('llama3:70b')
      })
    })

    it('empties the one it lacks rather than overwriting it', async () => {
      // An overwrite is saved: the other server's model replaces the real one.
      ollama(['llama3:70b'])
      renderFields({ analysis: 'qwen3:8b', generation: 'llama3:70b' })

      await waitFor(() => {
        expect(
          screen.getByRole('combobox', { name: 'Generation Model' }),
        ).toHaveValue('llama3:70b')
      })
      expect(
        screen.getByRole('combobox', { name: 'Analysis Model' }),
      ).toHaveValue('')
    })
  })
})
