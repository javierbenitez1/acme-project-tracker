import { describe, expect, it } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import useFormState from './useFormState';

describe('useFormState', () => {
  it('reports every failing rule and clears an error when its field changes', () => {
    const { result } = renderHook(() => useFormState({ name: '', email: '' }));
    let ok;
    act(() => { ok = result.current.check({ name: 'Enter a name.', email: false }); });
    expect(ok).toBe(false);
    expect(result.current.field('name').helperText).toBe('Enter a name.');
    expect(result.current.field('email').error).toBe(false);

    act(() => result.current.field('name').onChange({ target: { value: 'Grace' } }));
    expect(result.current.values.name).toBe('Grace');
    expect(result.current.field('name').error).toBe(false);
  });

  it('maps server field errors, including nested ones, onto fields', () => {
    const { result } = renderHook(() => useFormState({ user_ids: [] }));
    act(() => result.current.fail({
      message: 'Some users can\'t be added.', details: { user_ids: { 1: 'Alex is not an employee.' }, name: 'Too long.' },
    }));
    expect(result.current.formError).toBe("Some users can't be added.");
    expect(result.current.errors.user_ids).toBe('Alex is not an employee.');
    expect(result.current.errors.name).toBe('Too long.');
  });

  it('shows a hint when there is no error', () => {
    const { result } = renderHook(() => useFormState({ hours: '8' }));
    expect(result.current.field('hours', 'A full day is 8 hours.').helperText).toBe('A full day is 8 hours.');
  });
});