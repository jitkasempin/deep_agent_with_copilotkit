# MCP Widget Playground verification

Verified 2026-09-14 in `/root/my_new_ui/mcp-app`.

## Build and dependencies

- Required scaffold: `npx -y create-mcp-use-app@latest mcp-app --template mcp-apps`.
- Installed framework: `mcp-use@2.5.0`; generated dependency lockfile included in the deliverable directory (no local Git commit created).
- `npm run typecheck`: no type errors.
- `npm run build`: success, server plus `my-view` emitted to `.mcp-use/build`.
- Dependency installation audit: zero reported vulnerabilities.
- No standalone lint configuration is supplied by this template. TypeScript/biome LSP executables are unavailable; framework typechecking was run instead. No global tools were installed.

## Live MCP protocol checks

Driven through the production server at `http://localhost:3011/mcp` using HTTP JSON-RPC and through the development server using the mcp-use client CLI.

- MCP initialization and tool discovery pass.
- `show-app` returns matching text and structured content for omitted, empty, whitespace-only, and custom app names.
- `say-hello({name: "Alex"})` returns `Hello, Alex!`.
- Missing name, numeric name, and numeric appName are rejected.
- `resources/read` retrieves `ui://views/my-view.html` as `text/html;profile=mcp-app`.

## Real browser checks

Driven through the built-in Inspector using installed Chromium/Playwright. Screenshots captured through the framework screenshot command and the actual Inspector.

- The widget renders with its title and returned message.
- Clicking the counter twice changes it from 0 to 2.
- Clicking Say Hello makes a server call and displays `Tool Response: Hello, mcp-use!`.
- Fullscreen changes the View's host display mode and layout.
- Follow-up is correctly disabled when the Inspector does not advertise the message capability. A real model-host follow-up turn was not tested.
- Light, dark, and 375-pixel-wide rendering checked visually.
- Dark action buttons were given an opaque background to preserve contrast over the template's decorative orb.
- No JavaScript exceptions occurred in the final interaction run.

Artifacts: `widget-light.png`, `widget-dark.png`, `widget-narrow.png`, `inspector-interactions.png`, and `source-sha256.json`.

## Tooling observations

- The Inspector probes OAuth metadata on localhost. Its OAuth proxy returns HTTP 400 with `HTTPS is required`; these responses are from the bundled Inspector, not the app's tools. The example does not configure application OAuth.
- The screenshot command required a short post-render delay for reliable dark-mode painting and a WebSocket CDP URL in this root-run environment.
- The CLI's automatic optional client installation fails under npm 12 (`EALLOWSCRIPTS`). Installing `@mcp-use/client@2.3.1` with `--no-save --package-lock=false` enabled CLI verification without adding a project dependency.

## Deployment

User authorized a Manufact-managed repository. Deployment `c3748e3c-b291-4e8e-b477-df5321f31e4f` is running, server `94347ee7-db94-4b96-af17-9b10fc977874`. Managed source commit: `11e638b7cac12ea2ca9b92fc423d155fdf237c3a`.

- MCP endpoint: https://wild-pulse-2dr58.run.mcp-use.com/mcp
- Manufact dashboard: https://manufact.com/wild-pulse-2dr58
- Cloud build, platform health/stability checks, and production traffic switch completed successfully.
- Public HTTPS initialization, discovery, both tool calls, schema rejection, and View HTML retrieval all passed.
- View HTML contains no localhost references. `widget-cloud.png` captures the actual remote tool's rendered View.
- The browser Inspector connected to the public endpoint, called both `show-app` and `say-hello` over HTTPS, incremented the counter, and displayed the live greeting. No JavaScript exceptions occurred. Evidence: `inspector-cloud.png` and `cloud-verification.json`.

The local verification servers and Chromium debugging listener were stopped after cloud verification.
