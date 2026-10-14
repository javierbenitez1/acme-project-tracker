import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Box, Button, CircularProgress, Dialog, GlobalStyles, Stack, Table, TableBody, TableCell, TableHead, TableRow, Typography,
} from '@mui/material';
import AssessmentOutlined from '@mui/icons-material/AssessmentOutlined';
import CloseRounded from '@mui/icons-material/CloseRounded';
import PrintOutlined from '@mui/icons-material/PrintOutlined';
import { api } from '../services/api';
import { describeError } from '../utils/errors';
import { formatDate, formatMoney } from '../utils/format';

/** The report is a document, so it always uses print colors, even in dark mode. */
const INK = '#142033';
const MUTED = '#5B6678';
const LINE = '#D8DEE8';
const RAG = {
  green: { label: 'Green', color: '#2F8F5B', bg: '#E7F4EC' },
  amber: { label: 'Amber', color: '#B07A0E', bg: '#FBF1DD' },
  red: { label: 'Red', color: '#C2412D', bg: '#FBE6E2' },
};
const STATUS = { not_started: 'Not started', in_progress: 'In progress', blocked: 'Blocked', done: 'Done' };

const printStyles = (
  <GlobalStyles styles={{
    '@media print': {
      'body > #root': { display: 'none !important' },
      '.status-report, .status-report .MuiDialog-container, .status-report .MuiDialog-paper': {
        position: 'static !important', overflow: 'visible !important', height: 'auto !important',
        maxHeight: 'none !important', boxShadow: 'none !important', margin: '0 !important',
      },
      '.status-report .MuiBackdrop-root, .no-print': { display: 'none !important' },
      '@page': { margin: '14mm' },
    },
  }} />
);

function RagCard({ title, rag, big }) {
  const { label, color, bg } = RAG[rag.status];
  return (
    <Box sx={{ border: `1px solid ${LINE}`, borderTop: `4px solid ${color}`, borderRadius: '6px', p: 1.5, bgcolor: big ? bg : '#fff',
      breakInside: 'avoid' }}>
      <Typography sx={{ fontSize: 12, fontWeight: 700, color: MUTED, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{title}</Typography>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mt: 0.5 }}>
        <Box sx={{ width: 12, height: 12, borderRadius: '50%', bgcolor: color }} />
        <Typography sx={{ fontWeight: 700, fontSize: big ? 22 : 17, color: INK }}>{label}</Typography>
      </Box>
      <Typography sx={{ fontSize: 13, color: MUTED, mt: 0.5, lineHeight: 1.4 }}>{rag.reason}</Typography>
    </Box>
  );
}

function Heading({ children }) {
  return <Typography sx={{ fontWeight: 700, fontSize: 15, color: INK, mt: 3, mb: 1, pb: 0.5, borderBottom: `2px solid ${INK}` }}>{children}</Typography>;
}

const cell = { color: INK, borderColor: LINE, fontSize: 13, py: 0.75, px: 1 };
const head = { ...cell, color: MUTED, fontWeight: 700, fontSize: 12 };

function Report({ data }) {
  const { project, rag, forecast } = data;
  const finish = forecast?.projected_end ? formatDate(forecast.projected_end) : 'Not enough data yet';
  const numbers = [
    ['Progress', `${project.progress}%`],
    ['Time used', `${project.time_elapsed_pct}%`],
    ['Budget used', `${project.budget_used_pct}% of ${formatMoney(Number(project.budget_planned))}`],
    ['Forecast finish', forecast?.status === 'complete' ? 'Complete' : finish],
  ];
  return (
    <Box sx={{ maxWidth: 820, mx: 'auto', bgcolor: '#fff', color: INK, p: { xs: 2.5, sm: 5 }, fontFamily: 'inherit' }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 2, flexWrap: 'wrap' }}>
        <Typography sx={{ fontWeight: 800, letterSpacing: '0.12em', color: INK }}>ACME</Typography>
        <Typography sx={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', color: RAG.red.color, border: `1px solid ${RAG.red.color}`,
          px: 1, borderRadius: '4px' }}>INTERNAL USE ONLY</Typography>
      </Box>
      <Typography sx={{ fontSize: 13, color: MUTED, mt: 2.5, textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 600 }}>
        Weekly status report
      </Typography>
      <Typography component="h1" sx={{ fontSize: 28, fontWeight: 700, color: INK, lineHeight: 1.2 }}>{project.name}</Typography>
      <Typography sx={{ fontSize: 13, color: MUTED, mt: 0.5 }}>
        Prepared {formatDate(data.generated_at)} · Manager {project.manager_name}
        {project.department ? ` · ${project.department}` : ''} · {formatDate(project.start_date)} to {formatDate(project.end_date)}
      </Typography>

      <Box sx={{ display: 'grid', gap: 1.5, mt: 3, gridTemplateColumns: { xs: '1fr 1fr', sm: '1.3fr 1fr 1fr 1fr' } }}>
        <RagCard title="Overall" rag={rag.overall} big />
        <RagCard title="Schedule" rag={rag.schedule} />
        <RagCard title="Budget" rag={rag.budget} />
        <RagCard title="Risks" rag={rag.risks} />
      </Box>

      <Heading>Summary</Heading>
      <Typography sx={{ fontSize: 14, lineHeight: 1.6, color: INK }}>{data.summary}</Typography>
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr 1fr', sm: 'repeat(4, 1fr)' }, gap: 1.5, mt: 2 }}>
        {numbers.map(([label, value]) => (
          <Box key={label}>
            <Typography sx={{ fontSize: 12, color: MUTED }}>{label}</Typography>
            <Typography sx={{ fontSize: 16, fontWeight: 700, color: INK }}>{value}</Typography>
          </Box>
        ))}
      </Box>

      <Heading>Milestones</Heading>
      <Table size="small">
        <TableHead><TableRow>
          <TableCell sx={head}>Milestone</TableCell><TableCell sx={head}>Due</TableCell>
          <TableCell sx={head}>Status</TableCell><TableCell sx={head}>Can slip</TableCell>
        </TableRow></TableHead>
        <TableBody>
          {data.milestones.map((m) => (
            <TableRow key={`${m.name}-${m.start_date}`}>
              <TableCell sx={{ ...cell, fontWeight: m.critical ? 700 : 400 }}>{m.name}{m.critical ? ' (critical path)' : ''}</TableCell>
              <TableCell sx={cell}>{formatDate(m.end_date)}</TableCell>
              <TableCell sx={cell}>{STATUS[m.status] || m.status}</TableCell>
              <TableCell sx={cell}>{m.slack_days === null || m.slack_days === undefined ? '' : m.slack_days <= 0 ? 'No slack' : `${m.slack_days} days`}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <Heading>Top risks</Heading>
      {data.risks.length ? (
        <Table size="small">
          <TableHead><TableRow>
            <TableCell sx={head}>Risk</TableCell><TableCell sx={head}>Score</TableCell>
            <TableCell sx={head}>Owner</TableCell><TableCell sx={head}>Mitigation</TableCell>
          </TableRow></TableHead>
          <TableBody>
            {data.risks.map((r) => (
              <TableRow key={r.title}>
                <TableCell sx={{ ...cell, fontWeight: 600 }}>{r.title}</TableCell>
                <TableCell sx={{ ...cell, color: RAG[r.level === 'high' ? 'red' : r.level === 'medium' ? 'amber' : 'green'].color, fontWeight: 700 }}>
                  {r.score}
                </TableCell>
                <TableCell sx={cell}>{r.owner_name || 'Unassigned'}</TableCell>
                <TableCell sx={cell}>{r.mitigation || ''}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : <Typography sx={{ fontSize: 14, color: MUTED }}>No open risks are logged.</Typography>}

      <Heading>Needs attention</Heading>
      {data.attention.length ? (
        <Box component="ul" sx={{ m: 0, pl: 2.5 }}>
          {data.attention.map((a) => (
            <Typography component="li" key={a.title} sx={{ fontSize: 14, color: INK, mb: 0.5 }}>
              <b>{a.priority[0].toUpperCase() + a.priority.slice(1)}:</b> {a.title}
              {a.assignee_name ? `, ${a.assignee_name}` : ''}{a.due_date ? `, due ${formatDate(a.due_date)}` : ''}
            </Typography>
          ))}
        </Box>
      ) : <Typography sx={{ fontSize: 14, color: MUTED }}>Nothing is waiting on a decision.</Typography>}

      <Typography sx={{ fontSize: 11, color: MUTED, mt: 4, pt: 1.5, borderTop: `1px solid ${LINE}` }}>
        Generated by Throughline from live project data. Ratings follow fixed rules, so the colors always match the numbers.
        Internal use only.
      </Typography>
    </Box>
  );
}

/** "Status report" button for the project header: opens a printable one-page RAG report. */
export default function StatusReportButton({ project }) {
  const [open, setOpen] = useState(false);
  const report = useQuery({
    queryKey: ['project', String(project.id), 'report'],
    queryFn: () => api.get(`projects/${project.id}/report`),
    enabled: open,
  });
  return (
    <>
      <Button variant="outlined" startIcon={<AssessmentOutlined />} onClick={() => setOpen(true)}>Status report</Button>
      <Dialog open={open} onClose={() => setOpen(false)} fullScreen className="status-report"
        slotProps={{ paper: { sx: { bgcolor: '#EEF1F5' } } }}>
        {printStyles}
        <Box className="no-print" sx={{ position: 'sticky', top: 0, zIndex: 1, display: 'flex', alignItems: 'center', gap: 1, px: 2, py: 1.25,
          bgcolor: INK, color: '#fff', pt: 'calc(10px + env(safe-area-inset-top, 0px))' }}>
          <Typography sx={{ fontWeight: 600, flex: 1 }}>Weekly status report</Typography>
          <Button variant="contained" startIcon={<PrintOutlined />} onClick={() => window.print()} disabled={!report.data}>
            Print or save as PDF
          </Button>
          <Button color="inherit" startIcon={<CloseRounded />} onClick={() => setOpen(false)}>Close</Button>
        </Box>
        <Box sx={{ p: { xs: 0, sm: 3 } }}>
          {report.isPending && <Stack sx={{ alignItems: 'center', py: 10 }}><CircularProgress aria-label="Building the report" /></Stack>}
          {report.isError && <Typography sx={{ p: 4, color: RAG.red.color }}>{describeError(report.error)}</Typography>}
          {report.data && <Report data={report.data} />}
        </Box>
      </Dialog>
    </>
  );
}