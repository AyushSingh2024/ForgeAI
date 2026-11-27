"use client";

import { useRef, useState, type DragEvent } from "react";
import { bytes } from "@/lib/format";

export const ACCEPT = [".pdf", ".docx", ".md", ".txt", ".csv", ".xlsx", ".html", ".zip", ".png", ".jpg", ".jpeg"];
const MAX_MB = 25;

export default function DocUploader({ files, onChange }: { files: File[]; onChange: (f: File[]) => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [error, setError] = useState("");
  const [over, setOver] = useState(false);
  const total = files.reduce((s, f) => s + f.size, 0);

  function add(list: FileList | null) {
    if (!list) return;
    const incoming = Array.from(list);
    const bad = incoming.filter((f) => !ACCEPT.some((ext) => f.name.toLowerCase().endsWith(ext)));
    setError(bad.length ? `Not supported: ${bad.map((f) => f.name).join(", ")}` : "");
    const good = incoming.filter((f) => !bad.includes(f));
    const merged = [...files.filter((f) => !good.some((g) => g.name === f.name)), ...good];
    if (merged.reduce((s, f) => s + f.size, 0) > MAX_MB * 1024 * 1024) {
      setError(`Total size must stay under ${MAX_MB} MB.`);
      return;
    }
    onChange(merged);
  }

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setOver(false);
    add(e.dataTransfer.files);
  }

  return (
    <div className="space-y-2">
      <span className="font-medium">Documents</span>
      <div onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)} onDrop={onDrop}
        onClick={() => input.current?.click()}
        className="card cursor-pointer p-6 text-center"
        style={{ borderStyle: "dashed", borderColor: over ? "var(--accent)" : "var(--border)" }}>
        <p>Drop files here or click to choose</p>
        <p className="text-xs muted mt-1">{ACCEPT.join(" ")} · up to {MAX_MB} MB in total</p>
        <input ref={input} type="file" multiple hidden accept={ACCEPT.join(",")} onChange={(e) => add(e.target.files)} />
      </div>
      {error && <p className="text-sm" style={{ color: "var(--danger)" }}>{error}</p>}
      {files.length > 0 && (
        <ul className="card divide-y text-sm" style={{ borderColor: "var(--border)" }}>
          {files.map((f) => (
            <li key={f.name} className="flex items-center justify-between px-3 py-2">
              <span className="mono">{f.name}</span>
              <span className="flex items-center gap-3">
                <span className="muted">{bytes(f.size)}</span>
                <button type="button" className="text-xs" style={{ color: "var(--danger)" }}
                  onClick={() => onChange(files.filter((x) => x !== f))}>remove</button>
              </span>
            </li>
          ))}
          <li className="px-3 py-2 text-xs muted">
            {files.length} file(s), {bytes(total)}
            <div className="mt-1 h-1 rounded" style={{ background: "var(--border)" }}>
              <div className="h-1 rounded" style={{ width: `${Math.min(100, (total / (MAX_MB * 1024 * 1024)) * 100)}%`, background: "var(--accent)" }} />
            </div>
          </li>
        </ul>
      )}
    </div>
  );
}
