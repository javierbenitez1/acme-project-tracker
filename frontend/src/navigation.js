import SpaceDashboardOutlined from '@mui/icons-material/SpaceDashboardOutlined';
import AssignmentTurnedInOutlined from '@mui/icons-material/AssignmentTurnedInOutlined';
import WorkOutlineOutlined from '@mui/icons-material/WorkOutlineOutlined';
import FlagOutlined from '@mui/icons-material/FlagOutlined';
import ViewWeekOutlined from '@mui/icons-material/ViewWeekOutlined';
import PeopleAltOutlined from '@mui/icons-material/PeopleAltOutlined';
import Inventory2Outlined from '@mui/icons-material/Inventory2Outlined';
import ManageSearchOutlined from '@mui/icons-material/ManageSearchOutlined';

const EVERYONE = ['admin', 'manager', 'employee'];

/** One place that decides which pages each role can reach. The router and the menus both use it. */
export const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: SpaceDashboardOutlined, roles: EVERYONE, end: true },
  { to: '/my-work', label: 'My work', icon: AssignmentTurnedInOutlined, roles: ['employee'] },
  { to: '/projects', label: 'Projects', icon: WorkOutlineOutlined, roles: EVERYONE },
  { to: '/actions', label: 'Action Center', icon: FlagOutlined, roles: EVERYONE, badge: 'actions' },
  { to: '/workload', label: 'Workload', icon: ViewWeekOutlined, roles: ['admin', 'manager'] },
  { to: '/people', label: 'People', icon: PeopleAltOutlined, roles: ['admin', 'manager'] },
  { to: '/archive', label: 'Archive', icon: Inventory2Outlined, roles: ['admin'] },
  { to: '/audit', label: 'Audit log', icon: ManageSearchOutlined, roles: ['admin'] },
];

export const navItemsFor = (role) => NAV_ITEMS.filter((item) => item.roles.includes(role));

export const ROLE_LABELS = { admin: 'Administrator', manager: 'Manager', employee: 'Employee' };