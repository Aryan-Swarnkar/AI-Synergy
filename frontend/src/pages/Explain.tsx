import { useTranslation } from 'react-i18next'
import { MockBadge } from '../components/MockBadge'

const PRINCIPLES = [
  'Honesty over hype: KhadSetu cannot create fertiliser; it removes wasted trips and makes shortage visible and fair.',
  'Reservations expire: every token has an expiry; no-shows release stock and promote the waitlist.',
  'Stock data is untrusted: ledger + audits + discrepancies + safety buffer.',
  'Inclusion with guardrails: tenant / assisted / OTP-fallback paths are capped, flagged (needs_audit) and audited.',
  'Capacity-aware, not just nearest: scoring balances distance, crowd and wait within a detour tolerance.',
  'Same brain everywhere: one pure allocator drives the API and the simulator.',
  'Simulator is not rigged: mean ± std over seeds, sensitivity sweeps, auto-flagged losses.',
  'Everything external is mocked and labelled: OTP, Farmer ID, SMS/IVR, iFMS feed.',
]

const MOCKS: Array<[string, string]> = [
  ['OTP / voice / SMS', 'mock OTP 123456, voice 654321, SMS previews'],
  ['Farmer ID (AgriStack)', 'formatted MP-… strings at registration'],
  ['iFMS stock feed', 'operator receive-lot form'],
  ['IVR (Bhashini-class)', 'voice-callback fallback channel'],
]

export function Explain() {
  const { t } = useTranslation()
  return (
    <div className="grid gap-4">
      <div className="card">
        <h2 className="font-bold text-lg">{t('how.title')}</h2>
        <p className="text-sm mt-1">{t('tagline')}</p>
        <p className="text-sm mt-1 font-semibold">{t('honesty')}</p>
        <ol className="text-sm mt-2 ml-5 list-decimal grid gap-1">
          <li>Register (landowner / tenant-provisional / assisted)<MockBadge /></li>
          <li>Request with sowing date → allocator checks stock + slots before the deadline</li>
          <li>Token (centre, date, slot, QR) or honest waitlist with ETA</li>
          <li>Operator redeems → stock drops; audits log discrepancies; demo clock expires + promotes</li>
        </ol>
      </div>
      <div className="card">
        <h2 className="font-bold text-lg">{t('how.principles')}</h2>
        <ul className="list-disc ml-5 text-sm grid gap-1 mt-2">
          {PRINCIPLES.map((p) => <li key={p}>{p}</li>)}
        </ul>
      </div>
      <div className="card">
        <h2 className="font-bold text-lg">Mock map (integration-ready)</h2>
        <ul className="text-sm mt-2 grid gap-1">
          {MOCKS.map(([k, v]) => <li key={k}><b>{k}</b>: {v}<MockBadge /></li>)}
        </ul>
      </div>
    </div>
  )
}
