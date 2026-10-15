import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { MockBadge } from '../components/MockBadge'
import { Provenance } from '../components/Provenance'

type Proposal = {
  product?: string | null; crop?: string | null; acres?: number | null;
  sowing_date?: string | null; qty?: number | null; confidence: number;
  missing_fields: string[]; clarifying_question?: string | null; parser: string;
}

const EMPTY: Proposal = { confidence: 0, missing_fields: [], parser: 'rule' }

export function Intake() {
  const { t, i18n } = useTranslation()
  const [text, setText] = useState('mujhe 2 acre gehu ke liye urea chahiye, 10 din mein bona hai')
  const [prop, setProp] = useState<Proposal>(EMPTY)
  const [parsed, setParsed] = useState(false)
  const [msg, setMsg] = useState('')
  const [listening, setListening] = useState(false)
  const [tokenCode, setTokenCode] = useState('')
  // editable confirm fields
  const [f, setF] = useState({ product: 'UREA', crop: 'soybean', acres: '2', sowing_date: '2026-06-27', qty: '1' })
  const set = (k: string, v: string) => setF((p) => ({ ...p, [k]: v }))

  const parse = () =>
    api.post('/ai/parse', { text, lang: i18n.language }).then((r) => {
      const p = r as Proposal
      setProp(p)
      setParsed(true)
      setF({
        product: p.product ?? 'UREA', crop: p.crop ?? 'soybean',
        acres: p.acres !== null && p.acres !== undefined ? String(p.acres) : '',
        sowing_date: p.sowing_date ?? '', qty: p.qty !== null && p.qty !== undefined ? String(p.qty) : '',
      })
      setMsg('')
    }).catch((e) => setMsg(String(e)))

  const listen = () => {
    const SR = (window as unknown as { webkitSpeechRecognition?: new () => SpeechRec; SpeechRecognition?: new () => SpeechRec }).webkitSpeechRecognition
      ?? (window as unknown as { SpeechRecognition?: new () => SpeechRec }).SpeechRecognition
    if (!SR) { setMsg('Voice not supported in this browser — type instead.'); return }
    const rec = new SR()
    rec.lang = 'hi-IN'
    rec.onresult = (e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => {
      setText(e.results[0][0].transcript)
      setListening(false)
    }
    rec.onend = () => setListening(false)
    rec.onerror = () => { setListening(false); setMsg('Voice failed — type instead.') }
    setListening(true)
    rec.start()
  }
  type SpeechRec = { lang: string; onresult: unknown; onend: unknown; onerror: unknown; start(): void }

  const confirm = () =>
    api.post('/requests', {
      product: f.product, crop: f.crop, acres: Number(f.acres), qty: Number(f.qty),
      sowing_date: f.sowing_date, idempotency_key: `ai-${Date.now()}`,
      provenance: {
        ai_proposal: { ...prop },
        confirmed_edits: { product: f.product, crop: f.crop, acres: f.acres, sowing_date: f.sowing_date, qty: f.qty },
      },
    }).then((r) => {
      const v = r as { outcome: string; token_code?: string; reason_en?: string; reason?: string }
      setMsg(`${v.outcome}${v.reason_en ? `: ${v.reason_en}` : ''}${v.reason ? ` ${v.reason}` : ''}`)
      setTokenCode(v.token_code ?? '')
    }).catch((e) => setMsg(String(e)))

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <div className="card">
        <h2 className="font-bold text-lg mb-2">{t('intake.title')}<MockBadge /></h2>
        <textarea className="inp min-h-[96px]" value={text} onChange={(e) => setText(e.target.value)} aria-label="request text" />
        <div className="flex gap-2 mt-2">
          <button className="btn2" onClick={listen}>{listening ? '…' : '🎤'}</button>
          <button className="btn flex-1" onClick={parse}>{t('intake.parse')}</button>
        </div>
        <p className="text-xs mt-2"><Link className="underline text-blue-700" to="/request">{t('intake.form_fallback')}</Link></p>
        {msg && <p className="text-sm mt-2">{msg}</p>}
      </div>
      <div className="card">
        {!parsed && <p className="text-stone-500">—</p>}
        {parsed && (
          <div>
            <p className="text-sm">{t('intake.confidence')}: <b>{prop.confidence}</b> ({prop.parser})</p>
            {prop.clarifying_question && <p className="text-sm mt-1 text-amber-800">❓ {prop.clarifying_question}</p>}
            {prop.missing_fields.length > 0 && <p className="text-xs text-stone-500">missing: {prop.missing_fields.join(', ')}</p>}
            <div className="grid grid-cols-2 gap-2 mt-2">
              <div><label className="lbl">{t('request.product')}</label><input className="inp" value={f.product} onChange={(e) => set('product', e.target.value)} /></div>
              <div><label className="lbl">{t('request.crop')}</label><input className="inp" value={f.crop} onChange={(e) => set('crop', e.target.value)} /></div>
              <div><label className="lbl">{t('register.acres')}</label><input className="inp" value={f.acres} onChange={(e) => set('acres', e.target.value)} /></div>
              <div><label className="lbl">{t('request.qty')}</label><input className="inp" value={f.qty} onChange={(e) => set('qty', e.target.value)} /></div>
            </div>
            <label className="lbl mt-2">{t('request.sowing')}</label>
            <input type="date" className="inp" value={f.sowing_date} onChange={(e) => set('sowing_date', e.target.value)} />
            <button className="btn mt-3 w-full" onClick={confirm}>{t('intake.confirm')}</button>
            {tokenCode && <Provenance code={tokenCode} />}
          </div>
        )}
      </div>
    </div>
  )
}
