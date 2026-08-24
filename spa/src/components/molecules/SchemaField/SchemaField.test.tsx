import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type {
  PatchField,
  PatchKind,
} from '../../../libs/patchFields/patchFields.ts'
import { SchemaField } from './SchemaField.tsx'

/** A descriptor of one kind, as `libs/patchFields` would have built it. */
function field(kind: PatchKind, over: Partial<PatchField> = {}): PatchField {
  return {
    section: 'budget',
    field: 'tokens_per_track',
    name: 'budget.tokens_per_track',
    label: 'Tokens Per Track',
    kind,
    ...over,
  }
}

function renderField(one: PatchField, value: unknown) {
  return render(<SchemaField field={one} value={value} />)
}

describe('SchemaField', () => {
  it('names the input as the form addresses it', () => {
    renderField(field('text'), 'held')

    expect(screen.getByLabelText('Tokens Per Track')).toHaveAttribute(
      'name',
      'budget.tokens_per_track',
    )
  })

  it('shows the hint, which is the only documentation on the page', () => {
    renderField(field('text', { hint: 'What one track costs.' }), '')

    expect(screen.getByText('What one track costs.')).toBeVisible()
  })

  describe('text', () => {
    it('starts at the saved value', () => {
      renderField(field('text'), 'anthropic')

      expect(screen.getByLabelText('Tokens Per Track')).toHaveValue('anthropic')
    })

    it('starts empty where the section holds nothing for it', () => {
      renderField(field('text'), undefined)

      expect(screen.getByLabelText('Tokens Per Track')).toHaveValue('')
    })
  })

  describe('number', () => {
    it('carries the bounds the schema declared', () => {
      renderField(field('number', { min: 1, max: 400, step: 1 }), 12)

      const input = screen.getByLabelText('Tokens Per Track')
      expect(input).toHaveAttribute('min', '1')
      expect(input).toHaveAttribute('max', '400')
      expect(input).toHaveAttribute('step', '1')
    })

    it('takes decimals where the field is a float', () => {
      // A step of 1 makes a browser refuse a legal 0.6.
      renderField(field('number', { step: 'any' }), 0.6)

      expect(screen.getByLabelText('Tokens Per Track')).toHaveAttribute(
        'step',
        'any',
      )
    })

    it('leaves out a bound the schema did not declare', () => {
      renderField(field('number', { min: 1 }), 12)

      expect(screen.getByLabelText('Tokens Per Track')).not.toHaveAttribute(
        'max',
      )
    })
  })

  describe('boolean', () => {
    it('is a checkbox, ticked from the saved value', () => {
      renderField(field('boolean'), true)

      expect(screen.getByRole('checkbox')).toBeChecked()
    })

    it('is untouched where the section holds nothing for it', () => {
      renderField(field('boolean'), undefined)

      expect(screen.getByRole('checkbox')).not.toBeChecked()
    })
  })

  describe('password', () => {
    it('never carries the stored value into the page', () => {
      renderField(field('password'), 'sk-a-real-key')

      expect(screen.getByLabelText(/Tokens Per Track/)).toHaveValue('')
    })

    it('says one is stored, so a blank field does not read as unset', () => {
      renderField(field('password'), 'sk-a-real-key')

      expect(screen.getByLabelText(/Tokens Per Track/)).toHaveAttribute(
        'placeholder',
        expect.stringContaining('configured'),
      )
    })

    it('says a blank one keeps what is stored', () => {
      renderField(field('password'), 'sk-a-real-key')

      expect(
        screen.getByText(/Leave blank to keep the stored value/),
      ).toBeVisible()
    })
  })

  describe('list', () => {
    it('joins the saved items, which is how it is typed back', () => {
      renderField(field('list'), ['rock', 'jazz'])

      expect(screen.getByLabelText(/Tokens Per Track/)).toHaveValue(
        'rock, jazz',
      )
    })

    it('says how items are separated', () => {
      renderField(field('list'), [])

      expect(screen.getByText(/Comma-separated/)).toBeVisible()
    })
  })
})
