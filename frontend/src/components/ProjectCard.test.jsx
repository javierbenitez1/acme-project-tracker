import { describe, expect, it } from 'vitest';
import { screen } from '@testing-library/react';
import ProjectCard from './ProjectCard';
import { renderWithProviders } from '../test/render';

const project = {
  id: 3, name: 'Real-Time Fraud Alerts', manager_name: 'Priya Raman', department: 'Risk Technology', health: 'off_track',
  progress: 38, milestones_done: 1, milestone_count: 4, member_count: 5, budget_used_pct: 110, time_elapsed_pct: 57,
  days_remaining: 39, end_date: '2026-11-22', risk_reasons: ['1 overdue milestone', 'Over budget by $11,500'],
};

describe('ProjectCard', () => {
  it('summarizes the project and links to it', () => {
    renderWithProviders(<ProjectCard project={project} showBudget />);
    expect(screen.getByText('Real-Time Fraud Alerts')).toBeInTheDocument();
    expect(screen.getByText('Off track')).toBeInTheDocument();
    expect(screen.getByText('Priya Raman, Risk Technology')).toBeInTheDocument();
    expect(screen.getByText('1 of 4')).toBeInTheDocument();
    expect(screen.getByText('110%')).toBeInTheDocument();
    expect(screen.getByText('1 overdue milestone')).toBeInTheDocument();
    expect(screen.getByRole('link')).toHaveAttribute('href', '/projects/3');
  });

  it('shows time used instead of budget to employees', () => {
    renderWithProviders(<ProjectCard project={project} showBudget={false} />);
    expect(screen.queryByText('Budget used')).not.toBeInTheDocument();
    expect(screen.getByText('Time used')).toBeInTheDocument();
    expect(screen.getByText('57%')).toBeInTheDocument();
  });
});