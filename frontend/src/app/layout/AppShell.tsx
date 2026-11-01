import { NavLink, Outlet } from 'react-router-dom'
import { useCurrentAdmin, useLogout } from '../../features/auth/useAuth'
import { useAndroidBackButton } from '../../lib/androidBackButton'
import {
  BuildingIcon,
  BrandLogo,
  CashIcon,
  ClipboardIcon,
  MoreIcon,
  UsersIcon,
} from '../../components/icons'

const NAV_ITEMS = [
  { to: '/', label: 'Today', Icon: ClipboardIcon, end: true },
  { to: '/labourers', label: 'Labourers', Icon: UsersIcon },
  { to: '/sites', label: 'Sites', Icon: BuildingIcon },
  { to: '/payments', label: 'Payments', Icon: CashIcon },
  { to: '/more', label: 'More', Icon: MoreIcon },
] as const

export default function AppShell() {
  const { data: admin } = useCurrentAdmin()
  const logout = useLogout()
  useAndroidBackButton()

  return (
    <div className="flex h-full flex-col bg-slate-50">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 pt-[max(0.5rem,env(safe-area-inset-top))] pb-2">
        <h1 className="flex items-center" aria-label="Labour Management">
          <BrandLogo className="h-10 w-10 text-brand-500" />
          <span className="sr-only">Labour Management</span>
        </h1>
        {admin && (
          <button
            type="button"
            onClick={() => logout.mutate()}
            className="cursor-pointer text-sm text-slate-500 transition-colors active:text-slate-700"
          >
            {admin.name.split(' ')[0]} · Logout
          </button>
        )}
      </header>

      <main className="flex-1 overflow-y-auto pb-[max(5rem,calc(5rem+env(safe-area-inset-bottom)))]">
        <Outlet />
      </main>

      <nav className="fixed inset-x-0 bottom-0 border-t border-slate-200 bg-white pb-[env(safe-area-inset-bottom)]">
        <ul className="grid grid-cols-5">
          {NAV_ITEMS.map(({ to, label, Icon, ...rest }) => (
            <li key={to}>
              <NavLink
                to={to}
                end={'end' in rest ? rest.end : false}
                className={({ isActive }) =>
                  `flex min-h-14 cursor-pointer flex-col items-center justify-center gap-0.5 py-2 text-xs transition-colors ${
                    isActive ? 'font-semibold text-brand-600' : 'text-slate-500'
                  }`
                }
              >
                <Icon className="h-6 w-6" />
                {label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  )
}
