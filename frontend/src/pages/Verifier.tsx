import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { api } from '../api'

type Row = { id: number; name: string; phone: string; village_id: number; acres: number; type: string; landowner_name?: string }

export function Verifier() {
  const { t } = useTranslation()
  const [rows, setRows] = useState<Row[]>([])
  const [note, setNote] = useState('')
  const [msg, setMsg] = useState('')
  const [approved, setApproved] = useState(0)

  const load = () => { api.get('/verifier/pending').then((r) => setRows(r as Row[])).catch((e) => setMsg(String(e))) }
  useEffect(() => { load() }, [])

  const decide = (id: number, decision: string) =>
    api.post(`/verifier/${id}/decide`, { decision, note }).then(() => {
      if (decision === 'APPROVED') setApproved((n) => n + 1)
      load()
    }).catch((e) => setMsg(String(e)))

  return (
    <div className="card">
      <div className="flex items-center justify-between">
        <h2 className="font-bold text-lg">{t('ver.queue')} ({rows.length} pending · {approved}/40 approved today)</h2>
        <button className="btn2" onClick={load}>↻</button>
      </div>
      {msg && <p className="text-sm text-red-700">{msg}</p>}
      <input className="inp mt-2" placeholder={t('ver.note')} value={note} onChange={(e) => setNote(e.target.value)} />
      {rows.map((r) => (
        <div key={r.id} className="border rounded-lg p-3 mt-2">
          <p className="font-semibold">{r.name} · {r.phone}</p>
          <p className="text-sm">village {r.village_id} · {r.acres} ac · {r.type} · landowner: {r.landowner_name ?? '—'}</p>
          <div className="flex gap-2 mt-2">
            <button className="btn" onClick={() => decide(r.id, 'APPROVED')}>{t('ver.approve')}</button>
            <button className="btn2 !bg-red-100" onClick={() => decide(r.id, 'REJECTED')}>{t('ver.reject')}</button>
          </div>
        </div>
      ))}
      {rows.length === 0 && <p className="text-stone-500 mt-2">—</p>}
    </div>
  )
}
