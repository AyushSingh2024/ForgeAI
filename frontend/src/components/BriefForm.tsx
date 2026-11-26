"use client";

const EXAMPLES = {
  "HR policy assistant":
    "Build an assistant that helps new employees of a mid-size company understand leave, travel and expense, remote work and code-of-conduct policies. Answer in a friendly, plain-English tone with references to the policy section. Do not give legal advice, discuss individual salaries or make exceptions to policy.",
  "Ship spares assistant":
    "Build an assistant for a ship's chief engineer that finds spare parts in the inventory by part number or description, compares supplier lead times and warranty terms, estimates the cost of an order and checks the weather at the delivery port. It must not approve purchases or give safety-critical repair instructions.",
};

export default function BriefForm({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const n = value.trim().length;
  const ok = n >= 20 && n <= 3000;
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <label htmlFor="brief" className="font-medium">Brief</label>
        <select className="input w-auto text-sm" value="" onChange={(e) => e.target.value && onChange(EXAMPLES[e.target.value as keyof typeof EXAMPLES])}>
          <option value="">Insert example…</option>
          {Object.keys(EXAMPLES).map((k) => <option key={k} value={k}>{k}</option>)}
        </select>
      </div>
      <textarea id="brief" className="input min-h-36" value={value} onChange={(e) => onChange(e.target.value)}
        placeholder="One paragraph: who the agent is for, what it must answer, and what it must refuse." />
      <p className="text-xs muted">
        Say who it&apos;s for, what it must answer, and what it must refuse.{" "}
        <span style={{ color: ok || n === 0 ? "var(--muted)" : "var(--danger)" }}>{n}/3000 characters (min 20)</span>
      </p>
    </div>
  );
}
