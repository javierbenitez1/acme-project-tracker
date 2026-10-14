import { useState } from 'react';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import {
  Box, Button, InputAdornment, MenuItem, Skeleton, Stack, TextField, ToggleButton, ToggleButtonGroup, Typography,
} from '@mui/material';
import AddRounded from '@mui/icons-material/AddRounded';
import SearchRounded from '@mui/icons-material/SearchRounded';
import { useAuth } from '../auth/AuthContext';
import { api } from '../services/api';
import useDebounce from '../hooks/useDebounce';
import ProjectCard from '../components/ProjectCard';
import ProjectFormDialog from '../components/ProjectFormDialog';
import { EmptyState, ErrorState } from '../components/PageState';

const SORTS = [['health', 'Most urgent first'], ['end_date', 'Ending soonest'], ['progress', 'Least progress'], ['name', 'Name']];
const FILTERS = [['all', 'All'], ['attention', 'Needs attention'], ['on_track', 'On track']];
const SUBTITLES = {
  admin: 'Every active project at ACME. Completed and archived projects are in the Archive.',
  manager: 'The projects you manage.',
  employee: "The projects you're on.",
};
const GRID = { display: 'grid', gap: 2.5, gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))' };

export default function ProjectsPage() {
  const { user } = useAuth();
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [sort, setSort] = useState('health');
  const [creating, setCreating] = useState(false);
  const term = useDebounce(search.trim(), 300);
  const isAdmin = user.role === 'admin';

  const params = new URLSearchParams({ sort });
  if (term) params.set('search', term);
  if (filter === 'attention') params.set('at_risk', 'true');
  else if (filter !== 'all') params.set('health', filter);

  const projects = useQuery({
    queryKey: ['projects', params.toString()],
    queryFn: () => api.get(`projects?${params}`),
    placeholderData: keepPreviousData,
    refetchInterval: 30_000,
  });
  const filtered = Boolean(term) || filter !== 'all';

  let content;
  if (projects.isPending) {
    content = <Box sx={GRID}>{[0, 1, 2].map((i) => <Skeleton key={i} variant="rounded" height={240} />)}</Box>;
  } else if (projects.isError) {
    content = <ErrorState error={projects.error} onRetry={() => projects.refetch()} />;
  } else if (projects.data.length === 0) {
    content = filtered ? (
      <EmptyState title="No projects match" message="Try a different search or filter."
        action={<Button onClick={() => { setSearch(''); setFilter('all'); }}>Clear filters</Button>} />
    ) : (
      <EmptyState title="No projects yet"
        message={isAdmin ? 'Create the first project and assign it to a manager.' : "Projects will show up here once you're added to one."}
        action={isAdmin ? <Button variant="contained" onClick={() => setCreating(true)}>New project</Button> : null} />
    );
  } else {
    content = (
      <Box sx={{ ...GRID, opacity: projects.isPlaceholderData ? 0.6 : 1, transition: 'opacity 150ms' }}>
        {projects.data.map((project) => <ProjectCard key={project.id} project={project} showBudget={user.role !== 'employee'} />)}
      </Box>
    );
  }

  return (
    <Stack spacing={3}>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'flex-end', justifyContent: 'space-between' }}>
        <Box>
          <Typography variant="h1">Projects</Typography>
          <Typography color="text.secondary" sx={{ mt: 1 }}>{SUBTITLES[user.role]}</Typography>
        </Box>
        {isAdmin && <Button variant="contained" startIcon={<AddRounded />} onClick={() => setCreating(true)}>New project</Button>}
      </Box>

      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 2, alignItems: 'center' }}>
        <TextField size="small" fullWidth={false} placeholder="Search projects or managers" value={search}
          onChange={(event) => setSearch(event.target.value)} sx={{ flex: '1 1 260px', maxWidth: 420 }}
          slotProps={{
            input: { startAdornment: <InputAdornment position="start"><SearchRounded fontSize="small" /></InputAdornment> },
            htmlInput: { 'aria-label': 'Search projects' },
          }} />
        <ToggleButtonGroup size="small" exclusive value={filter} onChange={(_, value) => value && setFilter(value)} aria-label="Filter by health">
          {FILTERS.map(([value, label]) => <ToggleButton key={value} value={value} sx={{ px: 1.75 }}>{label}</ToggleButton>)}
        </ToggleButtonGroup>
        <TextField select size="small" fullWidth={false} label="Sort" value={sort} onChange={(event) => setSort(event.target.value)} sx={{ minWidth: 190 }}>
          {SORTS.map(([value, label]) => <MenuItem key={value} value={value}>{label}</MenuItem>)}
        </TextField>
      </Box>

      {content}
      {creating && <ProjectFormDialog onClose={() => setCreating(false)} />}
    </Stack>
  );
}