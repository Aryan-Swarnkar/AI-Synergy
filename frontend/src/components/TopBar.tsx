import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { MockBadge } from '../components/MockBadge'

const ROLES = ['farmer', 'operator', 'verifier', 'officer', 'sim'] as const

export function TopBar() {
  const { t, i18n } = useTranslation()
  const nav = useNavigate()
  const [role, setRole] = useState(localStorage.getItem('ks_role') ?? 'farmer')
  const [today, setToday] = useState('…')

  const refresh = () => {
    api.get('/health').then((h) => setToday((h as { demo_today: string }).demo_today)).catch(() => setToday('offline'))
  }
  useEffect(refresh, [])

  const switchRole = (r: string) => {
    setRole(r)
    localStorage.setItem('ks_role', r)
    localStorage.removeItem('ks_token')
    nav(r === 'farmer' ? '/login' : `/${r}`)
  }

  const tick = (date?: string) => {
    const q = date ? `?date=${date}` : ''
    api.post(`/admin/tick${q}`).then(refresh).catch((e) => alert(String(e)))
  }
  const addDays = (n: number) => {
    if (today === '…' || today === 'offline') return tick()
    const d = new Date(today)
    d.setDate(d.getDate() + n)
    tick(d.toISOString().slice(0, 10))
  }

  return (
    <header className="bg-green-800 text-white p-3 sticky top-0 z-10">
      <div className="flex flex-wrap items-center gap-2">
        <Link to="/how" className="font-bold text-lg">{t('app')}<MockBadge /></Link>
        <select className="text-black rounded px-2 py-2" value={role} onChange={(e) => switchRole(e.target.value)} aria-label="role">
          {ROLES.map((r) => <option key={r} value={r}>{t(`roles.${r}`)}</option>)}
        </select>
        <button className="btn2 !bg-green-700 !text-white border border-green-600" onClick={() => i18n.changeLanguage(i18n.language === 'en' ? 'hi' : 'en')}>
          {i18n.language === 'en' ? 'हिं' : 'EN'}
        </button>
        <span className="text-sm">{t('clock.today')}: <b>{today}</b></span>
        <button className="btn2 !bg-green-700 !text-white border border-green-600" onClick={() => addDays(1)}>{t('clock.plus1')}</button>
        <button className="btn2 !bg-green-700 !text-white border border-green-600" onClick={() => addDays(7)}>{t('clock.plus7')}</button>
        <button className="btn2 !bg-red-700 !text-white" onClick={() => api.post('/admin/reset-demo').then(refresh).catch((e) => alert(String(e)))}>{t('clock.reset')}</button>
      </div>
      <p className="text-xs mt-1 opacity-90">{t('honesty')}</p>
    </header>
  )
}
