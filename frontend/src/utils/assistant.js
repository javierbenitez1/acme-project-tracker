/** Helpers for the Ask Throughline chat: starter questions and a tiny formatter for its answers. */

export const STARTERS = {
  employee: ['What should I work on?', "What's due this week?", "What's blocked?", 'How do I mark something blocked?'],
  manager: ['Which projects are at risk?', "Who's overbooked?", "What's overdue?", "What's due this week?", 'How do I reschedule a milestone?'],
};

export const starterQuestions = (role) => (role === 'employee' ? STARTERS.employee : STARTERS.manager);

/** Splits "plain **bold** plain" into parts so React can render the bold bits without raw HTML. */
export function inlineParts(text) {
  return text.split(/(\*\*[^*]+\*\*)/).filter(Boolean).map((part) => (
    part.startsWith('**') && part.endsWith('**') ? { bold: true, text: part.slice(2, -2) } : { bold: false, text: part }
  ));
}

/** Turns an answer into blocks: paragraphs, and bullet lists for lines starting with "- ". */
export function answerBlocks(text) {
  const blocks = [];
  text.split('\n').filter((line) => line.trim()).forEach((line) => {
    if (line.startsWith('- ')) {
      const last = blocks[blocks.length - 1];
      const item = inlineParts(line.slice(2));
      if (last?.type === 'list') last.items.push(item);
      else blocks.push({ type: 'list', items: [item] });
    } else {
      blocks.push({ type: 'p', parts: inlineParts(line) });
    }
  });
  return blocks;
}

/** The project page the person is on, so "what's blocking it?" knows which project they mean. */
export function projectIdFromPath(pathname) {
  const match = /^\/projects\/(\d+)/.exec(pathname);
  return match ? Number(match[1]) : null;
}

/** How much of an answer to show at each step of the typing effect: a few words at a time. */
export function revealSteps(text, wordsPerStep = 3) {
  const words = text.split(/(\s+)/);
  const steps = [];
  for (let i = wordsPerStep * 2; i < words.length; i += wordsPerStep * 2) steps.push(words.slice(0, i).join(''));
  steps.push(text);
  return steps;
}