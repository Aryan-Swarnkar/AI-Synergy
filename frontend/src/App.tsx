import { useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { HashRouter, Link, Navigate, Route, Routes } from 'react-router-dom'
import { TopBar } from './components/TopBar'
import { Explain } from './pages/Explain'
import { Intake } from './pages/Intake'
import { Login } from './pages/Login'
import { MyTokens } from './pages/MyTokens'
import { NewRequest } from './pages/NewRequest'
import { Officer } from './pages/Officer'
import { Operator } from './pages/Operator'
import { Simulator } from './pages/Simulator'
import { Verifier } from './pages/Verifier'

function RoleLinks() {
  const { t } = useTranslation()
  const links: Array<[string, string]> = [
    ['/request', t('nav.request')], ['/intake', t('nav.intake')], ['/tokens', t('nav.tokens')],
    ['/operator', t('nav.operator')], ['/verifier', t('nav.verifier')],
    ['/officer', t('nav.officer')], ['/sim', t('nav.sim')], ['/how', t('nav.how')],
  ]
  return (
    <nav className="flex flex-wrap gap-2 p-3">
      {links.map(([to, label]) => <Link key={to} className="btn2" to={to}>{label}</Link>)}
    </nav>
  )
}

export function App() {
  const { i18n } = useTranslation()
  useEffect(() => { document.documentElement.lang = i18n.language }, [i18n.language])
  return (
    <HashRouter>
      <TopBar />
      <RoleLinks />
      <main className="p-3 max-w-5xl mx-auto pb-16">
        <Routes>
          <Route path="/" element={<Navigate to="/request" />} />
          <Route path="/login" element={<Login />} />
          <Route path="/request" element={<NewRequest />} />
          <Route path="/intake" element={<Intake />} />
          <Route path="/tokens" element={<MyTokens />} />
          <Route path="/operator" element={<Operator />} />
          <Route path="/verifier" element={<Verifier />} />
          <Route path="/officer" element={<Officer />} />
          <Route path="/sim" element={<Simulator />} />
          <Route path="/how" element={<Explain />} />
        </Routes>
      </main>
    </HashRouter>
  )
}
