import { describe, expect, it } from 'vitest';
import { answerBlocks, inlineParts, projectIdFromPath, revealSteps, starterQuestions } from './assistant';

describe('inlineParts', () => {
  it('marks bold text without using HTML', () => {
    expect(inlineParts('**Kiosk** is **at risk**.')).toEqual([
      { bold: true, text: 'Kiosk' }, { bold: false, text: ' is ' }, { bold: true, text: 'at risk' }, { bold: false, text: '.' },
    ]);
  });
});

describe('answerBlocks', () => {
  it('groups bullet lines into one list between paragraphs', () => {
    const blocks = answerBlocks('Two things:\n- **A** first\n- B second\nThat is all.');
    expect(blocks.map((b) => b.type)).toEqual(['p', 'list', 'p']);
    expect(blocks[1].items).toHaveLength(2);
    expect(blocks[1].items[0][0]).toEqual({ bold: true, text: 'A' });
  });
});

describe('projectIdFromPath', () => {
  it('finds the project page the person is on', () => {
    expect(projectIdFromPath('/projects/12')).toBe(12);
    expect(projectIdFromPath('/projects/12?tab=risks')).toBe(12);
    expect(projectIdFromPath('/workload')).toBeNull();
  });
});

describe('revealSteps', () => {
  it('reveals a few words at a time and always ends with the full answer', () => {
    const steps = revealSteps('one two three four five six seven', 3);
    expect(steps[0]).toBe('one two three ');
    expect(steps[steps.length - 1]).toBe('one two three four five six seven');
  });
});

describe('starterQuestions', () => {
  it('fits the role', () => {
    expect(starterQuestions('employee')).toContain('What should I work on?');
    expect(starterQuestions('admin')).toContain("Who's overbooked?");
  });
});