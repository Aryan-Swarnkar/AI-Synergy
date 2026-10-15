import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../api'
import { MockBadge } from '../components/MockBadge'

export function Login() {
  const { t } = useTranslation()
  const [phone, setPhone] = useState('9876501000')
  const [code, setCode] = useState('')
  const [fails, setFails] = useState(0)
  const [fb, setFb] = useState<string[] | null>(null)
  const [msg, setMsg] = useState('')
  // register form
  const [name, setName] = useState('Ramesh Patel')
  const [village, setVillage] = useState('38')
  const [acres, setAcres] = useState('2')
  const [ftype, setFtype] = useState('TENANT')

  const send = () => api.post('/otp/send', { phone }).then(() => setMsg('OTP sent (MOCK code 123456)')).catch((e) => setMsg(String(e)))
  const verify = () =>
    api.post('/otp/verify', { phone, code }).then((r) => {
      const v = r as { verified: boolean; fallback_options?: string[] }
      if (v.verified) { setMsg('Verified ✓'); setFails(0); setFb(null) }
      else { const n = fails + 1; setFails(n); setMsg(`Failed (${n})`); if (v.fallback_options) setFb(v.fallback_options) }
    }).catch((e) => setMsg(String(e)))

  const voice = () => api.post('/otp/voice-callback', { phone }).then((r) => setMsg(`Voice (MOCK): use ${(r as { spoken_code: string }).spoken_code}`)).catch((e) => setMsg(String(e)))

  const register = () =>
    api.post('/farmers/register', {
      name, phone, village_id: Number(village), acres: Number(acres), type: ftype,
      farmer_id_mock: ftype === 'LANDOWNER' ? 'MP-900001' : null,
    }).then((r) => {
      const f = r as { id: number }
      return api.login('FARMER', String(f.id))
    }).then(() => setMsg('Registered + logged in as FARMER ✓')).catch((e) => setMsg(String(e)))

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <div className="card">
        <h2 className="font-bold text-lg mb-2">{t('otp.title')}<MockBadge /></h2>
        <label className="lbl">{t('otp.phone')}</label>
        <input className="inp" value={phone} onChange={(e) => setPhone(e.target.value)} />
        <div className="flex gap-2 mt-2">
          <button className="btn" onClick={send}>{t('otp.send')}</button>
        </div>
        <label className="lbl mt-3">{t('otp.code')}</label>
        <input className="inp" value={code} onChange={(e) => setCode(e.target.value)} />
        <div className="flex gap-2 mt-2">
          <button className="btn" onClick={verify}>{t('otp.verify')}</button>
        </div>
        {fails >= 1 && <p className="mt-2"><a className="underline text-blue-700" href="#fb" onClick={(e) => e.preventDefault()}>{t('otp.notworking')}</a></p>}
        {fb && (
          <div id="fb" className="mt-2 grid gap-2">
            <p className="font-semibold">{t('otp.fallback')}</p>
            {fb.map((o) => <div key={o} className="card !bg-amber-50">
              <b>{o}</b>{o === 'VOICE_CALLBACK' && <button className="btn2 ml-2" onClick={voice}>Call me (MOCK)</button>}
            </div>)}
          </div>
        )}
        <p className="mt-2 text-sm">{msg}</p>
      </div>
      <div className="card">
        <h2 className="font-bold text-lg mb-2">{t('register.title')}<MockBadge /></h2>
        <label className="lbl">{t('register.name')}</label><input className="inp" value={name} onChange={(e) => setName(e.target.value)} />
        <label className="lbl mt-2">{t('register.type')}</label>
        <select className="inp" value={ftype} onChange={(e) => setFtype(e.target.value)}>
          <option value="LANDOWNER">{t('register.landowner')}</option>
          <option value="TENANT">{t('register.tenant')}</option>
        </select>
        <div className="grid grid-cols-2 gap-2 mt-2">
          <div><label className="lbl">{t('register.village')}</label><input className="inp" value={village} onChange={(e) => setVillage(e.target.value)} /></div>
          <div><label className="lbl">{t('register.acres')}</label><input className="inp" value={acres} onChange={(e) => setAcres(e.target.value)} /></div>
        </div>
        {ftype === 'TENANT' && <p className="text-sm mt-2 text-amber-800">{t('register.provisional')}</p>}
        <button className="btn mt-3 w-full" onClick={register}>{t('register.go')}</button>
      </div>
    </div>
  )
}
