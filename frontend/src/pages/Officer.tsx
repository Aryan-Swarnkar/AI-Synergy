import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet'
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, LineChart, Line } from 'recharts'
import 'leaflet/dist/leaflet.css'
import { api } from '../api'
import { MockBadge } from '../components/MockBadge'

type Centre = { id: number; name: string; lat: number; lon: number; health: string; available: number }
type Village = { id: number; name: string; lat: number; lon: number; pending_demand: number }

export function Officer() {
  const { t } = useTranslation()
  const [ov, setOv] = useState<Record<string, unknown> | null>(null)
  const [map, setMap] = useState<{ centres: Centre[]; villages: Village[] } | null>(null)
  const [mapFail, setMapFail] = useState(false)
  const [detour, setDetour] = useState('25')
  const [preview, setPreview] = useState('')
  const [msg, setMsg] = useState('')
  const [fc, setFc] = useState<{ forecast: Array<{ centre_id: number; product: string; week: number; qty: number }>; model_mae: number; naive_mae: number } | null>(null)
  const [flags, setFlags] = useState<Array<{ kind: string; entity: string; score: number; reason: string }>>([])

  const load = () => {
    api.get('/officer/overview').then((r) => setOv(r as Record<string, unknown>)).catch((e) => setMsg(String(e)))
    api.get('/officer/map').then((r) => setMap(r as { centres: Centre[]; villages: Village[] })).catch((e) => setMsg(String(e)))
    api.get('/ai/forecast').then((r) => setFc(r as typeof fc)).catch(() => undefined)
    api.get('/ai/anomalies').then((r) => setFlags((r as { flags: typeof flags }).flags)).catch(() => undefined)
  }
  useEffect(() => { load() }, [])

  const dismiss = (kind: string, entity: string) =>
    api.post('/ai/anomalies/dismiss', { kind, entity }).then(load).catch((e) => setMsg(String(e)))

  const rule = () => api.post('/officer/rule-preview', { overrides: { MAX_DETOUR_KM_OVER_NEAREST: Number(detour) } }).then((r) => setPreview(JSON.stringify(r, null, 1))).catch((e) => setMsg(String(e)))

  const demand = (ov?.demand_vs_supply ?? {}) as Record<string, { demand: number; supply: number }>
  const bars = Object.entries(demand).map(([p, v]) => ({ product: p, demand: v.demand, supply: v.supply }))
  const funnel = (ov?.token_funnel ?? {}) as Record<string, number>

  return (
    <div className="grid gap-4">
      <div className="card">
        <div className="flex items-center justify-between">
          <h2 className="font-bold text-lg">{t('off.overview')}</h2>
          <button className="btn2" onClick={load}>↻</button>
        </div>
        {msg && <p className="text-sm text-red-700">{msg}</p>}
        {bars.length > 0 && (
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={bars}>
              <XAxis dataKey="product" /><YAxis /><Tooltip /><Legend />
              <Bar dataKey="demand" fill="#b45309" /><Bar dataKey="supply" fill="#15803d" />
            </BarChart>
          </ResponsiveContainer>
        )}
        <p className="text-sm mt-2">{t('off.funnel')}: {JSON.stringify(funnel)}</p>
        <p className="text-sm">{t('off.waitlist')}: {String(ov?.waitlist_size ?? '—')}</p>
      </div>
      <div className="card">
        {!mapFail ? (
          <MapContainer center={[23.2, 77.4]} zoom={8} style={{ height: 320 }}>
            <TileLayer url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" eventHandlers={{ tileerror: () => setMapFail(true) }} />
            {map?.centres.map((c) => (
              <CircleMarker key={c.id} center={[c.lat, c.lon]} radius={10}
                pathOptions={{ color: c.health === 'ok' ? 'green' : c.health === 'low' ? 'orange' : 'red' }}>
                <Popup>{c.name} ({c.health})</Popup>
              </CircleMarker>
            ))}
          </MapContainer>
        ) : (
          <div><p>{t('off.mapFail')}</p>
            <ul className="text-sm list-disc ml-5">{map?.centres.map((c) => <li key={c.id}>{c.name} — {c.health} (avail {c.available})</li>)}</ul>
          </div>
        )}
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="card"><h2 className="font-bold">{t('off.atrisk')}</h2><pre className="text-xs overflow-auto">{JSON.stringify(ov?.at_risk ?? [], null, 1)}</pre></div>
        <div className="card"><h2 className="font-bold">{t('off.anomalies')}</h2><pre className="text-xs overflow-auto">{JSON.stringify(ov?.anomalies ?? [], null, 1)}</pre></div>
      </div>
      <div className="card">
        <h2 className="font-bold">Demand forecast (AI-2)<MockBadge /></h2>
        {fc && <p className="text-sm">model MAE {fc.model_mae} vs naive {fc.naive_mae} (synthetic history)</p>}
        {fc && (
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={fc.forecast.filter((r) => r.product === 'UREA').map((r) => ({ week: `C${r.centre_id} w${r.week}`, qty: r.qty }))}>
              <XAxis dataKey="week" tick={false} /><YAxis /><Tooltip />
              <Line dataKey="qty" stroke="#15803d" dot={false} />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
      <div className="card">
        <h2 className="font-bold">AI anomaly flags (AI-3)<MockBadge /></h2>
        {flags.length === 0 && <p className="text-sm text-stone-500">no flags</p>}
        {flags.map((f, i) => (
          <div key={i} className="border rounded-lg p-2 mt-2 text-sm flex justify-between items-center gap-2">
            <span><b>{f.kind}</b> {f.entity} (score {f.score}) — {f.reason}</span>
            <button className="btn2 !py-1 !min-h-[36px]" onClick={() => dismiss(f.kind, f.entity)}>Dismiss</button>
          </div>
        ))}
      </div>
      <div className="card">
        <h2 className="font-bold">{t('off.rule')}</h2>
        <div className="flex gap-2 mt-2">
          <input className="inp" value={detour} onChange={(e) => setDetour(e.target.value)} aria-label="max detour" />
          <button className="btn2" onClick={rule}>▶</button>
        </div>
        <pre className="text-xs overflow-auto mt-2">{preview || '—'}</pre>
      </div>
    </div>
  )
}
