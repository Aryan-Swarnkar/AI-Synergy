import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { QRCodeSVG } from 'qrcode.react'
import { api } from '../api'
import { MockBadge } from '../components/MockBadge'

type Res = {
  outcome: string; token_code?: string; centre_id?: number; pickup_date?: string;
  slot?: string; eta_date?: string; at_risk?: boolean; reason_en?: string;
  reason_hi?: string; reason?: string; token?: { code: string; centre: string; pickup_date: string; slot: string; expires_at: string };
}

export function NewRequest() {
  const { t, i18n } = useTranslation()
  const [product, setProduct] = useState('UREA')
  const [crop, setCrop] = useState('soybean')
  const [acres, setAcres] = useState('2')
  const [qty, setQty] = useState('1')
  const [sowing, setSowing] = useState('2026-06-27')
  const [res, setRes] = useState<Res | null>(null)
  const [msg, setMsg] = useState('')

  const submit = () =>
    api.post('/requests', {
      product, crop, acres: Number(acres), qty: Number(qty),
      sowing_date: sowing, idempotency_key: `web-${Date.now()}`,
    }).then((r) => { setRes(r as Res); setMsg('') }).catch((e) => setMsg(String(e)))

  const reason = res ? (i18n.language === 'hi' ? res.reason_hi : res.reason_en) ?? res.reason ?? '' : ''

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <div className="card">
        <h2 className="font-bold text-lg mb-2">{t('request.title')}</h2>
        <div className="grid grid-cols-2 gap-2">
          <div><label className="lbl">{t('request.product')}</label>
            <select className="inp" value={product} onChange={(e) => setProduct(e.target.value)}>
              {['UREA', 'DAP', 'MOP', 'NPK'].map((p) => <option key={p}>{p}</option>)}
            </select></div>
          <div><label className="lbl">{t('request.crop')}</label>
            <select className="inp" value={crop} onChange={(e) => setCrop(e.target.value)}>
              {['soybean', 'paddy', 'maize', 'cotton', 'wheat'].map((p) => <option key={p}>{p}</option>)}
            </select></div>
          <div><label className="lbl">{t('register.acres')}</label><input className="inp" value={acres} onChange={(e) => setAcres(e.target.value)} /></div>
          <div><label className="lbl">{t('request.qty')}</label><input className="inp" value={qty} onChange={(e) => setQty(e.target.value)} /></div>
        </div>
        <label className="lbl mt-2">{t('request.sowing')}</label>
        <input type="date" className="inp" value={sowing} min="2026-06-15" max="2026-07-30" onChange={(e) => setSowing(e.target.value)} />
        <button className="btn mt-3 w-full" onClick={submit}>{t('request.go')}</button>
        <p className="text-xs mt-2">{t('request.disclaimer')}</p>
        {msg && <p className="text-sm text-red-700 mt-2">{msg}</p>}
      </div>
      <div className="card">
        {!res && <p className="text-stone-500">—</p>}
        {res?.outcome === 'ISSUED' && res.token && (
          <div>
            <p className="text-3xl font-mono font-bold">{res.token.code}</p>
            <QRCodeSVG value={res.token.code} size={128} />
            <p className="mt-2">{res.token.centre} · {res.token.pickup_date} · {res.token.slot}</p>
            <p className="text-sm">{t('request.validUntil')}: {res.token.expires_at}</p>
            <div className="card !bg-green-50 mt-2"><b>{t('request.why')}:</b> {reason}</div>
          </div>
        )}
        {res?.outcome === 'WAITLISTED' && (
          <div>
            <p className="font-bold">{t('wait.position')}: — · {t('wait.eta')}: {res.eta_date ?? '—'}</p>
            {res.at_risk && <p className="text-red-700 font-semibold">{t('wait.atrisk')}</p>}
            <p className="text-sm">{t('wait.sms')} <MockBadge /></p>
            <p className="text-sm mt-1">{reason}</p>
          </div>
        )}
        {res?.outcome === 'REJECTED' && <p className="text-red-700 font-semibold">{reason}</p>}
      </div>
    </div>
  )
}
