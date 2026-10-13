import { Box, Typography } from '@mui/material';

export default function ComingSoon({ title, message = 'This page is being built next. The data behind it is already live in the API.' }) {
  return (
    <Box>
      <Typography variant="h1" gutterBottom>{title}</Typography>
      <Typography color="text.secondary">{message}</Typography>
    </Box>
  );
}