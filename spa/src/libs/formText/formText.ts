/**
 * One text field of a submitted form.
 *
 * `FormData.get` answers a `File` for a file input and null for a field that
 * was not submitted, so a bare `String(...)` on it can stringify an object.
 * Every action reads its fields through this instead.
 */
export function formText(form: FormData, name: string): string {
  const value = form.get(name)
  return typeof value === 'string' ? value : ''
}

/**
 * The last value submitted under one name.
 *
 * A checkbox is submitted behind a hidden `false` of the same name, so its
 * first entry is the default and its last is what the reader chose.
 */
export function formLast(form: FormData, name: string): string {
  const values = form.getAll(name)
  const last = values.at(-1)
  return typeof last === 'string' ? last : ''
}
