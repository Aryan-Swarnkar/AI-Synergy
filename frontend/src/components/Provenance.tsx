import { useState } from 'react'
import { api } from '../api'

export type ProvStep = { step: string; actor_type: string; actor: string; detail: unknown; ts: string }

const COLOR: Record<string, string> = { AI: 'bg-blue-600', RULE: 'bg-stone-500', HUMAN: 'bg-green-600' }

export function Provenance({ code }: { code: string }) {
  const [steps, setSteps] = useState<ProvStep[] | null>(null)
  const [open, setOpen] = useState(false)
  const load = () => {
    if (!open && steps === null) {
      api.get(`/tokens/${code}/provenance`)
        .then((r) => setSteps((r as { timeline: ProvStep[] }).timeline))
        .catch(() => setSteps([]))
    }
    setOpen(!open)
  }
  return (
    <div className="mt-2">
      <button className="btn2 !py-1 !min-h-[36px] text-sm" onClick={load}>
        {open ? '−' : '+'} Decision provenance
      </button>
      {open && (
        <ol className="mt-2 border-l-2 border-stone-300 ml-2">
          {(steps ?? []).map((s, i) => (
            <li key={i} className="ml-3 mb-2 flex gap-2 items-start">
              <span className={`mt-1 w-3 h-3 rounded-full shrink-0 ${COLOR[s.actor_type] ?? 'bg-stone-400'}`} title={s.actor_type} />
              <div className="text-sm">
                <b>{s.step}</b> <span className="text-xs text-stone-500">[{s.actor_type}] {s.actor}</span>
              </div>
            </li>
          ))}
          {steps !== null && steps.length === 0 && <p className="text-xs text-stone-500 ml-3">no steps recorded</p>}
        </ol>
      )}
    </div>
  )
}
