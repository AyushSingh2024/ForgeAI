# ForgeAI frontend

Next.js (App Router), TypeScript and Tailwind CSS, deployed on Vercel. Use it to upload a brief and documents, answer
the interview (at most 5 questions), watch the factory stages live, browse every artifact (requirements,
groundability, agent definition, evals, scores, change log, report) and chat with any generated agent.

## Local
```
npm install
copy .env.example .env.local      (NEXT_PUBLIC_API_URL=http://localhost:8000)
npm run dev                       (http://localhost:3000)
```

## Layout
- `src/app/`: pages (`/`, `/builds/new`, `/runs`, `/runs/[runId]`, `/runs/[runId]/interview`,
  `/runs/[runId]/report`, `/agents`, `/agents/[agentId]/chat`)
- `src/components/`: one component per artifact view
- `src/lib/api.ts`: the only code that calls the backend. `src/lib/types.ts` mirrors the backend schemas.
- `src/hooks/`: run polling and chat state

The frontend has no business logic: every number it shows comes from the backend's artifacts.
Deploy steps are in `../DEPLOY.md` (Vercel root directory `frontend`, env `NEXT_PUBLIC_API_URL` = the Render URL).
