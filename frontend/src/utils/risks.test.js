import { describe, expect, it } from 'vitest';
import { categoryLabel, matrixCells, registerSummary, riskLevel } from './risks';

describe('riskLevel', () => {
  it('uses the same bands as the server', () => {
    expect([25, 15, 14, 8, 7, 1].map(riskLevel)).toEqual(['high', 'high', 'medium', 'medium', 'low', 'low']);
  });
});

describe('registerSummary', () => {
  it('sums up active risks by level and flags overdue reviews', () => {
    expect(registerSummary({ active: 3, high: 1, medium: 0, low: 2, reviews_overdue: 1 }))
      .toBe('3 active risks: 1 high, 2 low. 1 review is overdue.');
  });

  it('handles an empty register', () => {
    expect(registerSummary({ active: 0 })).toBe('No active risks right now.');
    expect(registerSummary(undefined)).toBe('No active risks right now.');
  });
});

describe('matrixCells', () => {
  it('puts each risk in its likelihood and impact cell, severe impact on top', () => {
    const cells = matrixCells([{ id: 1, likelihood: 4, impact: 5 }, { id: 2, likelihood: 1, impact: 1 }]);
    expect(cells).toHaveLength(5);
    expect(cells[0][3]).toMatchObject({ impact: 5, likelihood: 4, level: 'high' });
    expect(cells[0][3].risks.map((r) => r.id)).toEqual([1]);
    expect(cells[4][0].risks.map((r) => r.id)).toEqual([2]);
  });
});

describe('categoryLabel', () => {
  it('turns stored values into labels', () => {
    expect(categoryLabel('resources')).toBe('People');
    expect(categoryLabel('unknown')).toBe('unknown');
  });
});