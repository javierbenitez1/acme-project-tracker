import { Fragment, useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import {
  Avatar, Box, Chip, Drawer, Fab, IconButton, InputBase, Stack, Tooltip, Typography,
} from '@mui/material';
import AutoAwesomeRounded from '@mui/icons-material/AutoAwesomeRounded';
import ArrowForwardRounded from '@mui/icons-material/ArrowForwardRounded';
import ArrowUpwardRounded from '@mui/icons-material/ArrowUpwardRounded';
import CloseRounded from '@mui/icons-material/CloseRounded';
import RestartAltRounded from '@mui/icons-material/RestartAltRounded';
import { useAuth } from '../auth/AuthContext';
import { api } from '../services/api';
import { describeError } from '../utils/errors';
import { answerBlocks, projectIdFromPath, revealSteps, starterQuestions } from '../utils/assistant';

const GRADIENT = 'linear-gradient(135deg, #4FB3B1 0%, #0B6E6E 55%, #142033 100%)';
const prefersReducedMotion = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;

function Sparkle({ size = 30 }) {
  return (
    <Avatar sx={{ width: size, height: size, background: GRADIENT, flexShrink: 0 }}>
      <AutoAwesomeRounded sx={{ fontSize: size * 0.55, color: '#fff' }} />
    </Avatar>
  );
}

function RichText({ text }) {
  return answerBlocks(text).map((block, i) => (block.type === 'list' ? (
    <Box component="ul" key={i} sx={{ m: 0, mt: 0.75, pl: 2.5 }}>
      {block.items.map((parts, j) => (
        <Typography component="li" variant="body2" key={j} sx={{ mb: 0.5, lineHeight: 1.55 }}>
          {parts.map((p, k) => (p.bold ? <b key={k}>{p.text}</b> : <Fragment key={k}>{p.text}</Fragment>))}
        </Typography>
      ))}
    </Box>
  ) : (
    <Typography variant="body2" key={i} sx={{ mt: i ? 0.75 : 0, lineHeight: 1.6 }}>
      {block.parts.map((p, k) => (p.bold ? <b key={k}>{p.text}</b> : <Fragment key={k}>{p.text}</Fragment>))}
    </Typography>
  )));
}

/** Shows an answer a few words at a time, like it's being written, unless the person prefers less motion. */
function TypedAnswer({ text, animate, onDone }) {
  const [shown, setShown] = useState(animate && !prefersReducedMotion() ? '' : text);
  useEffect(() => {
    if (shown === text) return undefined;
    const steps = revealSteps(text);
    let i = 0;
    const timer = setInterval(() => {
      setShown(steps[i]);
      i += 1;
      if (i >= steps.length) clearInterval(timer);
    }, 35);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text]);
  useEffect(() => {
    if (shown === text) onDone?.();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shown, text]);
  return <RichText text={shown || ' '} />;
}

function Thinking() {
  return (
    <Box role="status" aria-label="Thinking" sx={{ display: 'flex', gap: 0.6, alignItems: 'center', height: 22 }}>
      {[0, 1, 2].map((i) => (
        <Box key={i} sx={{
          width: 7, height: 7, borderRadius: '50%', bgcolor: 'primary.main',
          animation: 'askDot 1.2s infinite ease-in-out', animationDelay: `${i * 0.15}s`,
          '@keyframes askDot': { '0%, 80%, 100%': { opacity: 0.25, transform: 'translateY(0)' }, '40%': { opacity: 1, transform: 'translateY(-4px)' } },
          '@media (prefers-reduced-motion: reduce)': { animation: 'none', opacity: 0.6 },
        }} />
      ))}
    </Box>
  );
}

function Message({ message, onAsk, onOpen, animate, onTyped }) {
  const [typed, setTyped] = useState(!animate);
  if (message.role === 'user') {
    return (
      <Box sx={{ alignSelf: 'flex-end', maxWidth: '85%', bgcolor: 'primary.main', color: 'primary.contrastText',
        px: 1.75, py: 1, borderRadius: '16px 16px 4px 16px' }}>
        <Typography variant="body2" sx={{ lineHeight: 1.55, whiteSpace: 'pre-wrap' }}>{message.text}</Typography>
      </Box>
    );
  }
  const done = () => { setTyped(true); onTyped?.(); };
  return (
    <Box sx={{ display: 'flex', gap: 1.25, alignItems: 'flex-start', maxWidth: '100%' }}>
      <Sparkle size={28} />
      <Box sx={{ minWidth: 0, flex: 1, pt: 0.25 }}>
        {message.error ? (
          <Typography variant="body2" color="error.main">{message.text}</Typography>
        ) : (
          <TypedAnswer text={message.text} animate={animate} onDone={done} />
        )}
        {typed && message.links?.length > 0 && (
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, mt: 1.25 }}>
            {message.links.map((link) => (
              <Chip key={link.to} size="small" color="primary" variant="outlined" label={link.label}
                icon={<ArrowForwardRounded />} onClick={() => onOpen(link.to)} />
            ))}
          </Box>
        )}
        {typed && message.follow_ups?.length > 0 && (
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, mt: 1 }}>
            {message.follow_ups.slice(0, 4).map((q) => (
              <Chip key={q} size="small" variant="outlined" label={q} onClick={() => onAsk(q)} />
            ))}
          </Box>
        )}
      </Box>
    </Box>
  );
}

/** Ask Throughline: a chat panel that answers questions from live project data. Opened from a floating button. */
export default function AssistantPanel() {
  const { user } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [contextProject, setContextProject] = useState(null);
  const scrollRef = useRef(null);
  const inputRef = useRef(null);
  const pageProject = projectIdFromPath(location.pathname);

  const scrollDown = () => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  };
  useEffect(scrollDown, [messages, busy]);
  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 150);
  }, [open]);
  useEffect(() => {
    const onKey = (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'j') {
        event.preventDefault();
        setOpen((value) => !value);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  if (!user) return null;
  const first = user.name.split(' ')[0];

  async function ask(question) {
    const text = question.trim();
    if (!text || busy) return;
    setDraft('');
    setMessages((list) => [...list, { id: Date.now(), role: 'user', text }]);
    setBusy(true);
    try {
      const reply = await api.post('dashboard/ask', { question: text, project_id: pageProject || contextProject });
      setContextProject(reply.project_id || contextProject);
      setMessages((list) => [...list, { id: Date.now() + 1, role: 'assistant', ...reply }]);
    } catch (error) {
      setMessages((list) => [...list, { id: Date.now() + 1, role: 'assistant', error: true, text: describeError(error) }]);
    } finally {
      setBusy(false);
    }
  }

  const openLink = (to) => {
    navigate(to);
    setOpen(false);
  };

  return (
    <>
      <Tooltip title="Ask Throughline (Ctrl+J)" placement="left">
        <Fab variant="extended" color="primary" aria-label="Ask Throughline" onClick={() => setOpen(true)}
          sx={{
            position: 'fixed', right: 20, zIndex: 1200, background: GRADIENT, color: '#fff', fontWeight: 600,
            bottom: { xs: 'calc(80px + env(safe-area-inset-bottom, 0px))', md: 24 },
            display: open ? 'none' : 'inline-flex', boxShadow: '0 8px 24px rgba(11, 110, 110, 0.35)',
          }}>
          <AutoAwesomeRounded sx={{ mr: { xs: 0, sm: 1 } }} />
          <Box component="span" sx={{ display: { xs: 'none', sm: 'inline' } }}>Ask</Box>
        </Fab>
      </Tooltip>

      <Drawer anchor="right" open={open} onClose={() => setOpen(false)}
        slotProps={{ paper: { sx: { width: { xs: '100%', sm: 440 }, display: 'flex', flexDirection: 'column' } } }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5, px: 2, py: 1.5, borderBottom: 1, borderColor: 'divider',
          pt: 'calc(12px + env(safe-area-inset-top, 0px))' }}>
          <Sparkle size={36} />
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Typography sx={{ fontWeight: 700, lineHeight: 1.2 }}>Ask Throughline</Typography>
            <Typography variant="body2" color="text.secondary" noWrap>Answers from your live project data</Typography>
          </Box>
          {messages.length > 0 && (
            <Tooltip title="New conversation">
              <IconButton aria-label="Start a new conversation" onClick={() => { setMessages([]); setContextProject(null); }}>
                <RestartAltRounded />
              </IconButton>
            </Tooltip>
          )}
          <IconButton aria-label="Close" onClick={() => setOpen(false)}><CloseRounded /></IconButton>
        </Box>

        <Box ref={scrollRef} role="log" aria-live="polite" aria-label="Conversation"
          sx={{ flex: 1, overflowY: 'auto', px: 2, py: 2.5 }}>
          {messages.length === 0 ? (
            <Stack spacing={2} sx={{ alignItems: 'center', textAlign: 'center', pt: 4 }}>
              <Sparkle size={56} />
              <Typography variant="h6" sx={{ fontWeight: 700 }}>Hi {first}, what do you want to know?</Typography>
              <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 320 }}>
                Ask about risks, deadlines, workload or budgets, or how to do something in Throughline.
                {pageProject ? ' I can see which project you have open.' : ''}
              </Typography>
              <Stack spacing={1} sx={{ width: '100%', pt: 1 }}>
                {starterQuestions(user.role).map((q) => (
                  <Box key={q} component="button" type="button" onClick={() => ask(q)} sx={{
                    textAlign: 'left', font: 'inherit', fontSize: '0.875rem', color: 'text.primary', cursor: 'pointer',
                    bgcolor: 'action.hover', border: 1, borderColor: 'divider', borderRadius: '10px', px: 1.75, py: 1.25,
                    '&:hover, &:focus-visible': { borderColor: 'primary.main', outline: 'none' },
                  }}>
                    {q}
                  </Box>
                ))}
              </Stack>
            </Stack>
          ) : (
            <Stack spacing={2.25}>
              {messages.map((message, i) => (
                <Message key={message.id} message={message} onAsk={ask} onOpen={openLink} onTyped={scrollDown}
                  animate={message.role === 'assistant' && i === messages.length - 1} />
              ))}
              {busy && (
                <Box sx={{ display: 'flex', gap: 1.25, alignItems: 'center' }}>
                  <Sparkle size={28} />
                  <Thinking />
                </Box>
              )}
            </Stack>
          )}
        </Box>

        <Box component="form" onSubmit={(event) => { event.preventDefault(); ask(draft); }}
          sx={{ borderTop: 1, borderColor: 'divider', px: 2, pt: 1.5, pb: 'calc(10px + env(safe-area-inset-bottom, 0px))' }}>
          <Box sx={{ display: 'flex', alignItems: 'flex-end', gap: 1, border: 1, borderColor: 'divider', borderRadius: '14px',
            px: 1.5, py: 0.75, '&:focus-within': { borderColor: 'primary.main' } }}>
            <InputBase inputRef={inputRef} multiline maxRows={4} fullWidth value={draft} placeholder="Ask about your projects..."
              inputProps={{ 'aria-label': 'Your question', maxLength: 500 }}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault();
                  ask(draft);
                }
              }}
              sx={{ py: 0.5, fontSize: '0.95rem' }} />
            <IconButton type="submit" aria-label="Send" disabled={!draft.trim() || busy}
              sx={{ background: draft.trim() && !busy ? GRADIENT : undefined, color: '#fff', width: 34, height: 34,
                '&.Mui-disabled': { color: 'text.disabled' } }}>
              <ArrowUpwardRounded fontSize="small" />
            </IconButton>
          </Box>
          <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1, textAlign: 'center' }}>
            Answers are built from Throughline's live data with rules, not a generative AI model.
          </Typography>
        </Box>
      </Drawer>
    </>
  );
}