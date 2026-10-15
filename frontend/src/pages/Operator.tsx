import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { MockBadge } from '../components/MockBadge'

export function Operator() {
  const { t } = useTranslation()
  const [cid, setCid] = useState('1')
  const [dash, setDash] = useState('')
  const [code, setCode] = useState('')
  const [product, setProduct] = useState('UREA')
  const [qty, setQty] = useState('50')
  const [arrival, setArrival] = useState('2026-06-18')
  const [counted, setCounted] = useState('')
  const [msg, setMsg] = useState('')
  // assisted
  const [aname, setAname] = useState('')
  const [aphone, setAphone] = useState('')
  const [avillage, setAvillage] = useState('1')
  const [aacres, setAacres] = useState('1.5')

  const load = () => api.get(`/centres/${cid}/dashboard`).then((r) => setDash(JSON.stringify(r, null, 1))).catch((e) => setMsg(String(e)))
  const redeem = () => api.post(`/centres/${cid}/redeem`, { code }).then((r) => setMsg(JSON.stringify(r))).catch((e) => setMsg(String(e)))
  const receive = () => api.post(`/centres/${cid}/receive-lot`, { product, qty: Number(qty), arrival_date: arrival }).then(load).catch((e) => setMsg(String(e)))
  const audit = () => api.post(`/centres/${cid}/audit`, { product, counted_qty: Number(counted) }).then((r) => { setMsg(JSON.stringify(r)); load() }).catch((e) => setMsg(String(e)))
  const assisted = () => api.post('/farmers/assisted-register', { name: aname, phone: aphone, village_id: Number(avillage), acres: Number(aacres) }).then((r) => setMsg(JSON.stringify(r))).catch((e) => setMsg(String(e)))

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <div className="card">
        <h2 className="font-bold text-lg">{t('op.dashboard')}</h2>
        <div className="flex gap-2 mt-2">
          <input className="inp" value={cid} onChange={(e) => setCid(e.target.value)} aria-label="centre" />
          <button className="btn2" onClick={load}>↻</button>
        </div>
        <pre className="text-xs overflow-auto mt-2 max-h-96">{dash || '—'}</pre>
      </div>
      <div className="grid gap-4">
        <div className="card">
          <h2 className="font-bold">{t('op.redeem')}</h2>
          <input className="inp mt-2" placeholder={t('op.code')} value={code} onChange={(e) => setCode(e.target.value)} />
          <button className="btn mt-2 w-full" onClick={redeem}>{t('op.redeem')}</button>
        </div>
        <div className="card">
          <h2 className="font-bold">{t('op.receive')}<MockBadge /></h2>
          <div className="grid grid-cols-3 gap-2 mt-2">
            <input className="inp" value={product} onChange={(e) => setProduct(e.target.value)} />
            <input className="inp" value={qty} onChange={(e) => setQty(e.target.value)} />
            <input className="inp" value={arrival} onChange={(e) => setArrival(e.target.value)} />
          </div>
          <button className="btn mt-2 w-full" onClick={receive}>{t('op.go')}</button>
        </div>
        <div className="card">
          <h2 className="font-bold">{t('op.audit')}</h2>
          <input className="inp mt-2" placeholder={t('op.counted')} value={counted} onChange={(e) => setCounted(e.target.value)} />
          <button className="btn mt-2 w-full" onClick={audit}>{t('op.go')}</button>
        </div>
        <div className="card">
          <h2 className="font-bold">{t('op.assisted')}<MockBadge /></h2>
          <input className="inp mt-2" placeholder={t('register.name')} value={aname} onChange={(e) => setAname(e.target.value)} />
          <input className="inp mt-2" placeholder={t('otp.phone')} value={aphone} onChange={(e) => setAphone(e.target.value)} />
          <div className="grid grid-cols-2 gap-2 mt-2">
            <input className="inp" placeholder={t('register.village')} value={avillage} onChange={(e) => setAvillage(e.target.value)} />
            <input className="inp" placeholder={t('register.acres')} value={aacres} onChange={(e) => setAacres(e.target.value)} />
          </div>
          <button className="btn mt-2 w-full" onClick={assisted}>{t('op.go')}</button>
        </div>
        {msg && <div className="card"><pre className="text-xs overflow-auto">{msg}</pre></div>}
      </div>
    </div>
  )
}
