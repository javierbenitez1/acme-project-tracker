import { useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useMediaQuery } from 'react-responsive';
import { useQuery } from '@tanstack/react-query';
import {
  AppBar, Avatar, Badge, BottomNavigation, BottomNavigationAction, Box, Divider, Drawer, IconButton,
  List, ListItemButton, ListItemIcon, ListItemText, Menu, MenuItem, Paper, Toolbar, Tooltip, Typography,
} from '@mui/material';
import { useColorScheme } from '@mui/material/styles';
import DarkModeOutlined from '@mui/icons-material/DarkModeOutlined';
import LightModeOutlined from '@mui/icons-material/LightModeOutlined';
import { useAuth } from '../auth/AuthContext';
import { api } from '../services/api';
import { navItemsFor, ROLE_LABELS } from '../navigation';
import { ink } from '../theme';
import BrandMark from './BrandMark';

const DRAWER_WIDTH = 248;
const MOBILE_TABS = 4;

const initials = (name) => name.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0].toUpperCase()).join('');
const isActive = (item, pathname) => (item.end ? pathname === item.to : pathname === item.to || pathname.startsWith(`${item.to}/`));

export default function AppShell() {
  const { user, logout } = useAuth();
  const isMobile = useMediaQuery({ maxWidth: 899 });
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const { mode, setMode } = useColorScheme();
  const [menuAnchor, setMenuAnchor] = useState(null);

  const items = navItemsFor(user.role);
  const { data: summary } = useQuery({
    queryKey: ['actions', 'summary'],
    queryFn: () => api.get('actions/summary'),
    refetchInterval: 30_000,
  });
  const openActions = summary?.open_total ?? 0;
  const dark = mode === 'dark';
  const toggleMode = () => setMode(dark ? 'light' : 'dark');
  const closeMenu = () => setMenuAnchor(null);
  const badgeFor = (item) => (item.badge === 'actions' ? openActions : 0);

  const avatar = (size) => (
    <Avatar sx={{ width: size, height: size, bgcolor: '#4FB3B1', color: '#06201F', fontSize: size * 0.4, fontWeight: 700 }}>
      {initials(user.name)}
    </Avatar>
  );

  const accountMenu = (
    <Menu anchorEl={menuAnchor} open={Boolean(menuAnchor)} onClose={closeMenu}>
      <Box sx={{ px: 2, py: 1 }}>
        <Typography sx={{ fontWeight: 600 }}>{user.name}</Typography>
        <Typography variant="body2" color="text.secondary">{ROLE_LABELS[user.role]}</Typography>
      </Box>
      <Divider />
      {isMobile && items.slice(MOBILE_TABS).map((item) => (
        <MenuItem key={item.to} onClick={() => { closeMenu(); navigate(item.to); }}>{item.label}</MenuItem>
      ))}
      <MenuItem onClick={() => { closeMenu(); navigate('/profile'); }}>Your profile</MenuItem>
      <MenuItem onClick={() => { closeMenu(); toggleMode(); }}>{dark ? 'Switch to light mode' : 'Switch to dark mode'}</MenuItem>
      <Divider />
      <MenuItem onClick={() => { closeMenu(); logout(); }}>Sign out</MenuItem>
    </Menu>
  );

  const desktopNav = (
    <Drawer
      variant="permanent"
      sx={{
        width: DRAWER_WIDTH,
        flexShrink: 0,
        '& .MuiDrawer-paper': { width: DRAWER_WIDTH, bgcolor: ink, color: '#E6ECF4', borderRight: 0, display: 'flex', flexDirection: 'column' },
      }}
    >
      <Box sx={{ px: 2.5, py: 2.5, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <BrandMark color="#FFFFFF" />
        <Tooltip title={dark ? 'Switch to light mode' : 'Switch to dark mode'}>
          <IconButton onClick={toggleMode} aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'} sx={{ color: '#8E9BB0' }}>
            {dark ? <LightModeOutlined fontSize="small" /> : <DarkModeOutlined fontSize="small" />}
          </IconButton>
        </Tooltip>
      </Box>
      <List component="nav" aria-label="Main" sx={{ px: 1.5 }}>
        {items.map((item) => {
          const Icon = item.icon;
          return (
            <ListItemButton
              key={item.to}
              component={NavLink}
              to={item.to}
              end={item.end}
              sx={{
                borderRadius: 2,
                mb: 0.5,
                color: '#C9D3E1',
                '&:hover': { bgcolor: 'rgba(255,255,255,0.06)' },
                '&.active': { bgcolor: 'rgba(79,179,177,0.16)', color: '#FFFFFF', '& .MuiListItemIcon-root': { color: '#4FB3B1' } },
              }}
            >
              <ListItemIcon sx={{ minWidth: 38, color: '#8E9BB0' }}>
                <Badge color="error" badgeContent={badgeFor(item)} max={99}><Icon fontSize="small" /></Badge>
              </ListItemIcon>
              <ListItemText primary={item.label} slotProps={{ primary: { sx: { fontWeight: 500, fontSize: '0.9375rem' } } }} />
            </ListItemButton>
          );
        })}
      </List>
      <Box sx={{ mt: 'auto', p: 1.5 }}>
        <ListItemButton
          onClick={(event) => setMenuAnchor(event.currentTarget)}
          aria-haspopup="menu"
          aria-label="Account menu"
          sx={{ borderRadius: 2, color: '#E6ECF4', gap: 1.5 }}
        >
          {avatar(34)}
          <Box sx={{ minWidth: 0 }}>
            <Typography noWrap sx={{ fontWeight: 600, fontSize: '0.9rem' }}>{user.name}</Typography>
            <Typography noWrap variant="body2" sx={{ color: '#8E9BB0' }}>{ROLE_LABELS[user.role]}</Typography>
          </Box>
        </ListItemButton>
      </Box>
    </Drawer>
  );

  const mobileTabs = items.slice(0, MOBILE_TABS);
  const mobileNav = (
    <Paper sx={{ position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: 1100, borderTop: 1, borderColor: 'divider', pb: 'env(safe-area-inset-bottom)' }}>
      <BottomNavigation showLabels value={mobileTabs.findIndex((item) => isActive(item, pathname))} component="nav" aria-label="Main">
        {mobileTabs.map((item) => {
          const Icon = item.icon;
          return (
            <BottomNavigationAction
              key={item.to}
              component={NavLink}
              to={item.to}
              end={item.end}
              label={item.label}
              icon={<Badge color="error" badgeContent={badgeFor(item)} max={99}><Icon /></Badge>}
            />
          );
        })}
      </BottomNavigation>
    </Paper>
  );

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', bgcolor: 'background.default' }}>
      <a className="skip-link" href="#main">Skip to content</a>
      {!isMobile && desktopNav}
      <Box sx={{ flexGrow: 1, minWidth: 0, display: 'flex', flexDirection: 'column' }}>
        {isMobile && (
          <AppBar position="sticky" elevation={0} sx={{ bgcolor: ink }}>
            <Toolbar sx={{ justifyContent: 'space-between' }}>
              <BrandMark color="#FFFFFF" />
              <IconButton onClick={(event) => setMenuAnchor(event.currentTarget)} aria-label="Account menu" aria-haspopup="menu">
                {avatar(32)}
              </IconButton>
            </Toolbar>
          </AppBar>
        )}
        <Box
          component="main"
          id="main"
          tabIndex={-1}
          sx={{ flexGrow: 1, outline: 'none', width: '100%', maxWidth: 1440, mx: 'auto', p: { xs: 2, sm: 3, md: 4 }, pb: isMobile ? 11 : 4 }}
        >
          <Outlet />
        </Box>
      </Box>
      {isMobile && mobileNav}
      {accountMenu}
    </Box>
  );
}