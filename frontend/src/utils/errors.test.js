import { describe, expect, it } from 'vitest';
import { describeError } from './errors';

describe('describeError', () => {
  it('adds lists of names from the server to the message', () => {
    const error = { message: 'Experience design can\'t start until its dependencies are done.', details: { waiting_on: ['Discovery'] } };
    expect(describeError(error)).toBe("Experience design can't start until its dependencies are done. Waiting on: Discovery.");
  });

  it('ignores details that are not lists of names', () => {
    expect(describeError({ message: 'Too busy.', details: { available_hours: 2 } })).toBe('Too busy.');
  });

  it('falls back to a general message', () => {
    expect(describeError(undefined)).toMatch(/Something went wrong/);
  });
});