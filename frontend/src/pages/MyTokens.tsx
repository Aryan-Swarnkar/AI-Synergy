import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../api'

type Tok = { code: string; centre: string; pickup_date: string; slot: string; status: string; expires_at: string }

export function MyTokens() {
  const { t } = useTranslation()
  const [toks, setToks] = useState<Tok[]>([])
  const [wait, setWait] = useState<unknown[]>([])
  const [msg, setMsg] = useState('')

  const [banner, setBanner] = useState('')
  const [seen, setSeen] = useState<Set<string>>(new Set())

  const load = () => {
    api.get('/tokens/mine').then((r) => {
      const list = r as Tok[]
      const fresh = list.filter((x) => x.status === 'ISSUED' && !seen.has(x.code))
      if (seen.size > 0 && fresh.length > 0) setBanner(`🎉 You got a token! ${fresh.map((x) => x.code).join(', ')}`)
      setSeen(new Set(list.map((x) => x.code)))
      setToks(list)
    }).catch((e) => setMsg(String(e)))
    api.get('/waitlist/mine').then((r) => setWait(r as unknown[])).catch(() => undefined)
  }
  useEffect(() => { load() }, [])

  const act = (code: string, op: string) =>
    api.post(`/tokens/${code}/${op}`).then(load).catch((e) => setMsg(String(e)))

  return (
    <div className="grid gap-4">
      <div className="card">
        <div className="flex items-center justify-between">
          <h2 className="font-bold text-lg">{t('nav.tokens')}</h2>
          <button className="btn2" onClick={load}>↻</button>
        </div>
        {msg && <p className="text-sm text-red-700">{msg}</p>}
        {banner && <p className="mt-2 p-3 bg-green-100 border border-green-400 rounded-lg font-bold">{banner}</p>}
        {toks.map((x) => (
          <div key={x.code} className="border rounded-lg p-3 mt-2">
            <p className="font-mono font-bold">{x.code} <span className="text-xs bg-stone-200 rounded px-2 py-0.5">{x.status}</span></p>
            <p className="text-sm">{x.centre} · {x.pickup_date} · {x.slot} · valid till {x.expires_at}</p>
            {x.status === 'ISSUED' && <div className="flex gap-2 mt-2">
              <button className="btn2" onClick={() => act(x.code, 'reschedule')}>{t('request.reschedule')}</button>
              <button className="btn2" onClick={() => act(x.code, 'cancel')}>{t('request.cancel')}</button>
            </div>}
          </div>
        ))}
        {toks.length === 0 && <p className="text-stone-500 mt-2">—</p>}
      </div>
      <div className="card">
        <h2 className="font-bold text-lg">{t('off.waitlist')}</h2>
        <pre className="text-xs overflow-auto">{JSON.stringify(wait, null, 1)}</pre>
      </div>
    </div>
  )
}
