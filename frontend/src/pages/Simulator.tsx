import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, LineChart, Line } from 'recharts'
import { api } from '../api'
import { MockBadge } from '../components/MockBadge'

type Agg = Record<string, { base_mean: number; base_std: number; kh_mean: number; kh_std: number }>

export function Simulator() {
  const { t } = useTranslation()
  const [preset, setPreset] = useState('normal')
  const [presets, setPresets] = useState<string[]>(['normal', 'shortage_20pct', 'high_otp_failure', 'rush_week', 'data_error_5pct'])
  const [farmers, setFarmers] = useState('1500')
  const [seeds, setSeeds] = useState('1,2,3')
  const [runId, setRunId] = useState('')
  const [status, setStatus] = useState('')
  const [agg, setAgg] = useState<Agg | null>(null)
  const [findings, setFindings] = useState<string[]>([])
  const [sensParam, setSensParam] = useState('supply_ratio')
  const [sensValues, setSensValues] = useState('0.7,0.8,0.9,1.0,1.1')
  const [sens, setSens] = useState<Array<Record<string, unknown>>>([])
  const [msg, setMsg] = useState('')

  useEffect(() => { api.get('/sim/presets').then((r) => setPresets(Object.keys((r as { presets: object }).presets))).catch(() => undefined) }, [])

  const run = () => {
    setMsg('running…')
    api.post('/sim/run', {
      params: { n_farmers: Number(farmers), ...(preset !== 'normal' ? presetParams() : {}) },
      seeds: seeds.split(',').map((s) => Number(s.trim())).filter((n) => !isNaN(n)),
    }).then((r) => {
      const id = (r as { run_id: string }).run_id
      setRunId(id)
      poll(id)
    }).catch((e) => setMsg(String(e)))
  }

  const presetParams = (): Record<string, number> => {
    const table: Record<string, Record<string, number>> = {
      shortage_20pct: { supply_ratio: 0.8 }, high_otp_failure: { otp_fail_rate: 0.4 },
      rush_week: { supply_ratio: 0.9, no_show_rate: 0.15 }, data_error_5pct: { shrinkage: 0.05 },
    }
    return table[preset] ?? {}
  }

  const poll = (id: string) => {
    const iv = setInterval(() => {
      api.get(`/sim/${id}`).then((r) => {
        const s = r as { status: string; progress: number; result?: { agg: Agg; findings: string[] } }
        setStatus(`${s.status} ${Math.round((s.progress ?? 0) * 100)}%`)
        if (s.status === 'done' && s.result) {
          clearInterval(iv)
          setAgg(s.result.agg)
          setFindings(s.result.findings)
          setMsg('')
        } else if (s.status === 'failed') { clearInterval(iv); setMsg('run failed') }
      }).catch((e) => { clearInterval(iv); setMsg(String(e)) })
    }, 1000)
  }

  const sweep = () =>
    api.post('/sim/sensitivity', {
      param: sensParam, values: sensValues.split(',').map(Number),
      seeds: [1, 2], params: { n_farmers: Number(farmers) },
    }).then((r) => setSens((r as { series: Array<Record<string, unknown>> }).series)).catch((e) => setMsg(String(e)))

  const bar = (key: string) => agg ? [{ k: 'baseline', v: agg[key].base_mean }, { k: 'khadsetu', v: agg[key].kh_mean }] : []
  const sensLine = sens.map((row) => ({
    value: row.value as number,
    base: ((row.served_in_window_pct ?? {}) as { base_mean?: number }).base_mean,
    kh: ((row.served_in_window_pct ?? {}) as { kh_mean?: number }).kh_mean,
  }))

  return (
    <div className="grid gap-4">
      <div className="card">
        <h2 className="font-bold text-lg">Simulator<MockBadge /></h2>
        <p className="text-sm">{t('honesty')}</p>
        <div className="grid grid-cols-3 gap-2 mt-2">
          <select className="inp" value={preset} onChange={(e) => setPreset(e.target.value)} aria-label={t('simPage.preset')}>
            {presets.map((p) => <option key={p}>{p}</option>)}
          </select>
          <input className="inp" value={farmers} onChange={(e) => setFarmers(e.target.value)} aria-label={t('simPage.farmers')} />
          <input className="inp" value={seeds} onChange={(e) => setSeeds(e.target.value)} aria-label={t('simPage.seeds')} />
        </div>
        <button className="btn mt-2 w-full" onClick={run}>{t('simPage.run')}</button>
        <p className="text-sm mt-1">{runId && `run ${runId}: ${status}`} {msg}</p>
      </div>
      {agg && (
        <div className="grid gap-4 md:grid-cols-2">
          {[['served_in_window_pct', 'served in window %'], ['wasted_trips_per_farmer', 'wasted/farmer'], ['avg_travel_km_per_served', 'km/served']].map(([k, label]) => (
            <div key={k} className="card"><h3 className="font-bold text-sm">{label}</h3>
              <ResponsiveContainer width="100%" height={180}>
                <BarChart data={bar(k)}><XAxis dataKey="k" /><YAxis /><Tooltip /><Bar dataKey="v" fill="#15803d" /></BarChart>
              </ResponsiveContainer>
            </div>
          ))}
        </div>
      )}
      {findings.length > 0 && (
        <div className="card !bg-amber-50">
          <h2 className="font-bold">{t('simPage.where')}</h2>
          <ul className="list-disc ml-5 text-sm">{findings.map((f, i) => <li key={i}>{f}</li>)}</ul>
        </div>
      )}
      <div className="card">
        <h2 className="font-bold">Sensitivity</h2>
        <div className="grid grid-cols-2 gap-2 mt-2">
          <input className="inp" value={sensParam} onChange={(e) => setSensParam(e.target.value)} />
          <input className="inp" value={sensValues} onChange={(e) => setSensValues(e.target.value)} />
        </div>
        <button className="btn2 mt-2" onClick={sweep}>▶</button>
        {sensLine.length > 0 && (
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={sensLine}><XAxis dataKey="value" /><YAxis /><Tooltip /><Legend />
              <Line dataKey="base" stroke="#b45309" /><Line dataKey="kh" stroke="#15803d" />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
      <div className="card">
        <details><summary className="font-bold cursor-pointer">{t('simPage.method')}</summary>
          <p className="text-sm mt-2">Baseline is our model of the described queue-token system (tenants excluded, OTP blocks the day, no stock check, wasted trips on dry counters), not measured data. Same allocator core as the live API. Mean ± std over seeds. Single product (UREA).</p>
        </details>
        {agg && <div className="flex gap-2 mt-2">
          <button className="btn2" onClick={() => {
            const blob = new Blob([JSON.stringify({ agg, findings }, null, 1)], { type: 'application/json' })
            const a = document.createElement('a')
            a.href = URL.createObjectURL(blob); a.download = 'sim.json'; a.click()
          }}>{t('simPage.export')} JSON</button>
          <button className="btn2" onClick={() => {
            const rows = ['metric,baseline_mean,baseline_std,khadsetu_mean,khadsetu_std']
            for (const [k, v] of Object.entries(agg)) rows.push(`${k},${v.base_mean},${v.base_std},${v.kh_mean},${v.kh_std}`)
            const blob = new Blob([rows.join('\n')], { type: 'text/csv' })
            const a = document.createElement('a')
            a.href = URL.createObjectURL(blob); a.download = 'sim.csv'; a.click()
          }}>{t('simPage.export')} CSV</button>
        </div>}
      </div>
    </div>
  )
}
