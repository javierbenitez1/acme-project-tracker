import { Box, Typography } from '@mui/material';
import useElementWidth from '../../hooks/useElementWidth';
import { formatMoney, parseDate } from '../../utils/format';

const HEIGHT = 240;
const PAD = { top: 20, right: 24, bottom: 30, left: 64 };
const monthKey = (date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;

/** Cumulative spending by month against the planned budget, with a dashed forecast to the end date. */
export default function BurnChart({ project, summary }) {
  const [ref, width] = useElementWidth();
  const start = parseDate(project.start_date);
  const end = parseDate(project.end_date);
  const months = [];
  for (let d = new Date(start.getFullYear(), start.getMonth(), 1); d <= end; d = new Date(d.getFullYear(), d.getMonth() + 1, 1)) {
    months.push(d);
  }
  const nowKey = monthKey(new Date());
  const cumulative = Object.fromEntries(summary.monthly.map((m) => [m.month, m.cumulative]));
  const actual = [];
  let running = 0;
  months.forEach((month, i) => {
    const key = monthKey(month);
    if (key > nowKey) return;
    if (cumulative[key] !== undefined) running = cumulative[key];
    actual.push({ i, value: running });
  });

  const planned = summary.planned;
  const projected = summary.forecast.projected_total;
  // Round the axis to a tidy step (1, 2, 2.5 or 5 times a power of ten) so labels read like $200K, $400K
  const rawTop = Math.max(planned, projected || 0, summary.spent, 1) * 1.08;
  const magnitude = 10 ** Math.floor(Math.log10(rawTop / 4));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((candidate) => candidate * 4 >= rawTop);
  const top = step * 4;
  const yTicks = [0, 1, 2, 3, 4].map((k) => k * step);
  const innerW = Math.max(width - PAD.left - PAD.right, 1);
  const innerH = HEIGHT - PAD.top - PAD.bottom;
  const x = (i) => PAD.left + (months.length > 1 ? (i / (months.length - 1)) * innerW : innerW / 2);
  const y = (value) => PAD.top + (1 - value / top) * innerH;
  const last = actual[actual.length - 1];
  const line = actual.map((p, k) => `${k ? 'L' : 'M'}${x(p.i)},${y(p.value)}`).join(' ');
  const area = actual.length ? `${line} L${x(last.i)},${y(0)} L${x(actual[0].i)},${y(0)} Z` : '';
  const showForecast = Boolean(projected) && last && last.i < months.length - 1;
  const forecastColor = summary.forecast.status === 'over' ? 'var(--mui-palette-error-main)' : 'var(--mui-palette-warning-main)';
  const labelEvery = Math.ceil(months.length / 8) || 1;
  const description = `Spending reached ${formatMoney(summary.spent)} of a ${formatMoney(planned)} plan`
    + `${projected ? `, forecast to finish at ${formatMoney(projected)}` : ''}.`;

  return (
    <Box>
      <Box ref={ref} sx={{ width: '100%', height: HEIGHT }}>
        {width > 0 && (
          <svg width={width} height={HEIGHT} role="img" aria-label={description}>
            {yTicks.map((value) => (
              <g key={value}>
                <line x1={PAD.left} x2={width - PAD.right} y1={y(value)} y2={y(value)} stroke="var(--mui-palette-divider)" />
                <text x={PAD.left - 8} y={y(value) + 4} textAnchor="end" fontSize="11" fill="var(--mui-palette-text-secondary)">
                  {formatMoney(value, { compact: true })}
                </text>
              </g>
            ))}
            {months.map((month, i) => (i % labelEvery === 0 || i === months.length - 1) && (
              <text key={monthKey(month)} x={x(i)} y={HEIGHT - 8} textAnchor="middle" fontSize="11" fill="var(--mui-palette-text-secondary)">
                {month.toLocaleDateString('en-US', { month: 'short' })}
              </text>
            ))}
            {planned > 0 && (
              <g>
                <line x1={PAD.left} x2={width - PAD.right} y1={y(planned)} y2={y(planned)} stroke="var(--mui-palette-text-primary)" strokeDasharray="6 4" strokeWidth="1.5" />
                <text x={width - PAD.right} y={y(planned) - 6} textAnchor="end" fontSize="12" fontWeight="600" fill="var(--mui-palette-text-primary)">
                  Plan {formatMoney(planned, { compact: true })}
                </text>
              </g>
            )}
            {area && <path d={area} fill="var(--mui-palette-primary-main)" opacity="0.14" />}
            {line && <path d={line} fill="none" stroke="var(--mui-palette-primary-main)" strokeWidth="2.5" strokeLinejoin="round" />}
            {actual.map((p) => <circle key={p.i} cx={x(p.i)} cy={y(p.value)} r="3.5" fill="var(--mui-palette-primary-main)" />)}
            {showForecast && (
              <g>
                <line x1={x(last.i)} y1={y(last.value)} x2={x(months.length - 1)} y2={y(projected)} stroke={forecastColor} strokeWidth="2" strokeDasharray="5 5" />
                <circle cx={x(months.length - 1)} cy={y(projected)} r="4" fill="none" stroke={forecastColor} strokeWidth="2" />
              </g>
            )}
          </svg>
        )}
      </Box>
      <Box sx={{ display: 'flex', flexWrap: 'wrap', columnGap: 3, rowGap: 1, mt: 1.5, color: 'text.secondary', fontSize: '0.8125rem' }}>
        <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 1 }}><Box component="span" sx={{ width: 18, height: 3, bgcolor: 'primary.main' }} />Spent to date</Box>
        <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 1 }}><Box component="span" sx={{ width: 18, borderTop: '2px dashed', borderColor: 'text.primary' }} />Planned budget</Box>
        {showForecast && <Box sx={{ display: 'inline-flex', alignItems: 'center', gap: 1 }}><Box component="span" sx={{ width: 18, borderTop: `2px dashed ${forecastColor}` }} />Forecast at the current pace</Box>}
      </Box>
      <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>{description}</Typography>
    </Box>
  );
}