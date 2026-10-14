import { useState } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import {
  Avatar, Box, Button, Card, Collapse, InputAdornment, Link, MenuItem, Pagination, Skeleton, Stack, Table, TableBody,
  TableCell, TableHead, TableRow, TextField, Typography,
} from '@mui/material';
import AutoModeOutlined from '@mui/icons-material/AutoModeOutlined';
import DownloadRounded from '@mui/icons-material/DownloadRounded';
import SearchRounded from '@mui/icons-material/SearchRounded';
import { api } from '../services/api';
import useDebounce from '../hooks/useDebounce';
import { EmptyState, ErrorState } from '../components/PageState';
import { ROLE_LABELS } from '../navigation';
import { initials, timeAgo, toIsoDate } from '../utils/format';

const PAGE_SIZE = 25;
const humanize = (text) => text.replace(/[._]/g, ' ').replace(/^./, (c) => c.toUpperCase());
const show = (value) => (value === null || value === undefined || value === '' ? 'empty' : String(value));

function downloadCsv(items) {
  const rows = [['When', 'Who', 'Role', 'Action', 'Project', 'Summary'],
    ...items.map((e) => [e.created_at, e.actor_name || 'Automatic', e.actor_role || '', e.action, e.project_name || '', e.summary])];
  const csv = rows.map((row) => row.map((cell) => `"${String(cell).replaceAll('"', '""')}"`).join(',')).join('\n');
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }));
  const link = document.createElement('a');
  link.href = url;
  link.download = `audit-log-${toIsoDate(new Date())}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

function Details({ details }) {
  if (!details) return <Typography variant="body2" color="text.secondary">No extra details were recorded.</Typography>;
  const { changes, ...rest } = details;
  return (
    <Stack spacing={1.5}>
      {changes && Object.keys(changes).length > 0 && (
        <Table size="small" aria-label="Changed fields" sx={{ maxWidth: 720 }}>
          <TableHead><TableRow><TableCell>Field</TableCell><TableCell>Before</TableCell><TableCell>After</TableCell></TableRow></TableHead>
          <TableBody>
            {Object.entries(changes).map(([field, change]) => (
              <TableRow key={field}>
                <TableCell>{humanize(field)}</TableCell>
                <TableCell sx={{ color: 'text.secondary' }}>{show(change.from)}</TableCell>
                <TableCell sx={{ fontWeight: 600 }}>{show(change.to)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      {Object.entries(rest).map(([key, value]) => (
        <Typography key={key} variant="body2"><strong>{humanize(key)}:</strong> {Array.isArray(value) ? value.join(', ') : show(value)}</Typography>
      ))}
    </Stack>
  );
}

export default function AuditPage() {
  const [search, setSearch] = useState('');
  const [action, setAction] = useState('');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState(null);
  const term = useDebounce(search.trim(), 300);

  const params = new URLSearchParams({ page, page_size: PAGE_SIZE });
  if (term) params.set('search', term);
  if (action) params.set('action', action);
  if (from) params.set('from', from);
  if (to) params.set('to', to);
  const audit = useQuery({ queryKey: ['audit', params.toString()], queryFn: () => api.get(`audit?${params}`), placeholderData: keepPreviousData, refetchInterval: 30_000 });
  const resetPage = (setter) => (event) => { setter(event.target.value); setPage(1); };
  const data = audit.data;

  return (
    <Stack spacing={3}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 2, flexWrap: 'wrap' }}>
        <Box>
          <Typography variant="h1">Audit log</Typography>
          <Typography color="text.secondary" sx={{ mt: 1, maxWidth: 720 }}>
            Every change anyone makes, with before and after values. Entries can't be edited or deleted.
          </Typography>
        </Box>
        <Button startIcon={<DownloadRounded />} onClick={() => downloadCsv(data?.items || [])} disabled={!data?.items?.length}>Download this page as CSV</Button>
      </Box>

      <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
        <TextField size="small" fullWidth={false} placeholder="Search what happened" value={search} onChange={resetPage(setSearch)} sx={{ flex: '1 1 260px', maxWidth: 380 }}
          slotProps={{ input: { startAdornment: <InputAdornment position="start"><SearchRounded fontSize="small" /></InputAdornment> }, htmlInput: { 'aria-label': 'Search the audit log' } }} />
        <TextField select size="small" fullWidth={false} label="Action" value={action} onChange={resetPage(setAction)} sx={{ minWidth: 220 }}>
          <MenuItem value="">All actions</MenuItem>
          {(data?.available_actions || []).map((a) => <MenuItem key={a} value={a}>{humanize(a)}</MenuItem>)}
        </TextField>
        <TextField size="small" fullWidth={false} type="date" label="From" value={from} onChange={resetPage(setFrom)} slotProps={{ inputLabel: { shrink: true } }} />
        <TextField size="small" fullWidth={false} type="date" label="To" value={to} onChange={resetPage(setTo)} slotProps={{ inputLabel: { shrink: true } }} />
      </Box>

      {audit.isPending ? <Skeleton variant="rounded" height={420} />
        : audit.isError ? <ErrorState error={audit.error} onRetry={() => audit.refetch()} />
          : data.items.length === 0 ? <EmptyState title="No matching entries" message="Try a wider date range or a different search." />
            : (
              <Card sx={{ opacity: audit.isPlaceholderData ? 0.6 : 1 }}>
                <Box component="ol" sx={{ listStyle: 'none', m: 0, p: 0 }}>
                  {data.items.map((entry) => {
                    const expanded = open === entry.id;
                    return (
                      <Box component="li" key={entry.id} sx={{ px: { xs: 2, md: 3 }, py: 1.75, borderBottom: 1, borderColor: 'divider', '&:last-child': { borderBottom: 0 } }}>
                        <Box sx={{ display: 'flex', gap: 1.75, alignItems: 'flex-start' }}>
                          <Avatar aria-hidden="true" sx={{ width: 34, height: 34, fontSize: '0.8rem', fontWeight: 700, bgcolor: entry.actor_name ? 'primary.main' : 'action.selected', color: entry.actor_name ? 'primary.contrastText' : 'text.secondary' }}>
                            {entry.actor_name ? initials(entry.actor_name) : <AutoModeOutlined fontSize="small" />}
                          </Avatar>
                          <Box sx={{ flexGrow: 1, minWidth: 0 }}>
                            <Typography>{entry.summary}</Typography>
                            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.25 }}>
                              {entry.actor_name ? `${entry.actor_name}, ${ROLE_LABELS[entry.actor_role] || entry.actor_role}` : 'Automatic'}
                              {', '}<span title={new Date(entry.created_at).toLocaleString()}>{timeAgo(entry.created_at)}</span>
                              {', '}{humanize(entry.action)}
                              {entry.project_name && <>{', '}<Link component={RouterLink} to={`/projects/${entry.project_id}`} underline="hover">{entry.project_name}</Link></>}
                            </Typography>
                            {entry.details && (
                              <Button size="small" sx={{ mt: 0.5, px: 0 }} aria-expanded={expanded} onClick={() => setOpen(expanded ? null : entry.id)}>
                                {expanded ? 'Hide details' : 'Show details'}
                              </Button>
                            )}
                            <Collapse in={expanded} unmountOnExit><Box sx={{ pt: 1 }}><Details details={entry.details} /></Box></Collapse>
                          </Box>
                        </Box>
                      </Box>
                    );
                  })}
                </Box>
              </Card>
            )}

      {data && data.total > PAGE_SIZE && (
        <Box sx={{ display: 'flex', justifyContent: 'center' }}>
          <Pagination count={Math.ceil(data.total / PAGE_SIZE)} page={page} onChange={(_, value) => setPage(value)} color="primary" />
        </Box>
      )}
      {data && <Typography variant="body2" color="text.secondary" sx={{ textAlign: 'center' }}>{data.total} entries</Typography>}
    </Stack>
  );
}