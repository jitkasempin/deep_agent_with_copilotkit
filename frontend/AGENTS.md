# Repository Guidelines

## Project Structure & Module Organization

`frontend/` contains the Lesson 3 React 19/TypeScript application. The Python backend, `L3.ipynb`, and independent `mcp-app/` demo live in the parent directory.

- `src/`: application, reusable `components/`, `hooks/`, and `globals.css`.
- `e2e/`: browser tests; `playwright.config.ts` configures execution.
- `index.html`: browser entry point.
- `server.ts` and `watch-server.ts`: CopilotKit runtime and development watcher.

## Build, Test, and Development Commands

Run commands from `frontend/`:

- `npm install`: install dependencies.
- `npm run dev -- --port 3003`: start Vite and the CopilotKit runtime on port 4003.
- `npm run build`: create the production bundle.
- `npm run preview`: serve the built bundle locally.
- `npx tsc --noEmit`: check TypeScript without generating files.
- `PLAYWRIGHT_BASE_URL=http://127.0.0.1:3003 npm run test:e2e`: run browser tests.

Start the lesson backend on port 8003 using the parent notebook before testing integrated behavior.

## Coding Style & Naming Conventions

Use strict TypeScript, ESM imports, two-space indentation, double quotes, and semicolons. Use PascalCase for component exports and kebab-case for reusable component files. Prefer `@/` imports for `src/` and Tailwind utilities plus `globals.css` variables for styling.

Generative components export a Zod `{Component}Props` schema, infer props with `z.infer`, and register that schema with `useComponent()`. No lint or formatter script is configured; match nearby code.

## Testing Guidelines

Use Playwright/Chromium and name specs `e2e/*.spec.ts`. Tests require an already-running frontend/runtime/backend stack. No coverage threshold is configured. `lesson2-frontend.spec.ts` still expects the old App Mode/todo interface; update it for Lesson 3 before treating it as a regression gate.

## Commit & Pull Request Guidelines

Git history is unavailable in this checkout. Use concise intent-focused commit subjects and Lore trailers such as `Tested:`, `Confidence:`, and `Scope-risk:` where useful. Pull requests should describe behavior, link relevant issues, list verification results, and include screenshots for UI changes.

## Configuration & Notebook Safety

Keep `GOOGLE_API_KEY` in a local `.env`; never commit secrets. `LANGGRAPH_DEPLOYMENT_URL` overrides the backend URL. Coordinate `src/App.tsx` changes with `../L3.ipynb`, whose cells can rewrite it.
