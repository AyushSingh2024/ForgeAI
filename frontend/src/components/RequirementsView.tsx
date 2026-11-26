import type { Requirements } from "@/lib/types";

const Badge = ({ text, color }: { text: string; color: string }) => (
  <span className="rounded px-1.5 py-0.5 text-xs" style={{ border: `1px solid ${color}`, color }}>{text}</span>
);

export default function RequirementsView({ req }: { req: Requirements }) {
  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-3">
        <div className="card p-4"><p className="text-xs muted">Audience</p><p>{req.audience.who} ({req.audience.expertise})</p></div>
        <div className="card p-4"><p className="text-xs muted">Tone</p><p>{req.tone.style}, formality {req.tone.formality}</p></div>
        <div className="card p-4"><p className="text-xs muted">Output</p><p>{req.output_preferences.format}, ≤ {req.output_preferences.max_words} words</p></div>
      </section>
      <section>
        <h3 className="font-semibold mb-2">Scope</h3>
        <p className="text-sm"><b>In:</b> {req.scope.in_scope.join("; ") || "-"}</p>
        <p className="text-sm"><b>Out:</b> {req.scope.out_of_scope.join("; ") || "-"}</p>
      </section>
      <section>
        <h3 className="font-semibold mb-2">Must answer</h3>
        <table className="data"><thead><tr><th>id</th><th>topic</th><th>example question</th></tr></thead>
          <tbody>{req.must_answer.map((m) => (
            <tr key={m.id}><td className="mono">{m.id}</td><td>{m.topic}</td><td className="muted">{m.example_question}</td></tr>
          ))}</tbody></table>
      </section>
      <section>
        <h3 className="font-semibold mb-2">Must refuse</h3>
        <table className="data"><thead><tr><th>topic</th><th>reason</th><th>source</th></tr></thead>
          <tbody>{req.must_refuse.map((m) => (
            <tr key={m.id}><td>{m.topic}</td><td className="muted">{m.reason}</td>
              <td>{m.source === "guard" ? <Badge text="guard" color="var(--warning)" /> : m.source}</td></tr>
          ))}</tbody></table>
      </section>
      <section>
        <h3 className="font-semibold mb-2">Interview ({req.interview.length} of max 5)</h3>
        {req.interview.length === 0 ? <p className="muted text-sm">No questions were needed.</p> : (
          <table className="data"><thead><tr><th>question</th><th>answer</th><th>source</th></tr></thead>
            <tbody>{req.interview.map((t) => (
              <tr key={t.question_id}><td>{t.question}</td><td>{t.answer || <span className="muted">(kept default)</span>}</td>
                <td>{t.source === "assumed" ? <Badge text="assumed" color="var(--warning)" /> : t.source}</td></tr>
            ))}</tbody></table>
        )}
      </section>
    </div>
  );
}
