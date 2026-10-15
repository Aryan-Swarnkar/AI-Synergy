import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet'
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import 'leaflet/dist/leaflet.css'
import { api } from '../api'

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

  const load = () => {
    api.get('/officer/overview').then((r) => setOv(r as Record<string, unknown>)).catch((e) => setMsg(String(e)))
    api.get('/officer/map').then((r) => setMap(r as { centres: Centre[]; villages: Village[] })).catch((e) => setMsg(String(e)))
  }
  useEffect(() => { load() }, [])

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
