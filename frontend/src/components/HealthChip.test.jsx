import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import HealthChip from './HealthChip';
import { renderWithProviders } from '../test/render';

describe('HealthChip', () => {
  it.each([
    ['on_track', 'On track'],
    ['at_risk', 'At risk'],
    ['off_track', 'Off track'],
    ['completed', 'Completed'],
  ])('always shows a text label for %s, not just a color', (value, label) => {
    renderWithProviders(<HealthChip value={value} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });
});