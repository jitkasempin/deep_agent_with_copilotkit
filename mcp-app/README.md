# MCP Widget Playground

A working MCP Apps example built with mcp-use 2.5.0 and the official `mcp-apps` template. It runs independently of the lesson frontend and Python backend in the parent directory. No API keys are needed for the demo.

## Run locally

Requires Node.js 22.22.2 or newer. From this directory:

```bash
npm ci
npm run dev
```

Open [the Inspector](http://localhost:3000/mcp/inspector), select `show-app`, and click **Execute**. The MCP endpoint is **http://localhost:3000/mcp**. Connect an MCP Apps-compatible host to this endpoint and ask it to open the widget playground.

To use a different port, run `npm run dev -- --port 3010`. Production mode:

```bash
npm run typecheck
npm run build
npm start
```

To inspect the production build locally, use `npm start -- --with-inspector`.

## Try the tools and widget

| Tool | Input | Result |
| --- | --- | --- |
| `show-app` | `{}` or `{"appName":"My Demo"}` | Opens the interactive widget with a default or custom title. |
| `say-hello` | `{"name":"Alex"}` | Returns `Hello, Alex!` as text and structured data. |

Inside the widget:

- **Update State** increments the counter and shares its current value with the host model.
- **Say Hello** calls the server's greeting tool and displays the result.
- **Send Followup** sends a prompt to the host when that capability is available.
- Host-supported controls open documentation, fullscreen, or picture-in-picture.
- The mounted View also exposes `set-counter` to hosts supporting View tools.

Counter state belongs to the mounted widget and resets when it is reopened. Themes and display modes follow the host. Text-only MCP clients can call the tools but do not render the widget.

The server is defined in `index.ts`; the widget is in `views/my-view/view.tsx`. Both tools export typed references used by `mcp-env.d.ts`.

## Deploy on Manufact Cloud

```bash
npx mcp-use login
npx mcp-use deploy --no-github -y --start-command "npm start -- --host 0.0.0.0"
```

This uploads this project's source to a Manufact-managed private repository. The CLI returns the public MCP endpoint and the Manufact dashboard URL. Cloud account sign-in is required. The example endpoint has no application authentication and exposes only the demo tools.

For a repository in your own GitHub account, install the mcp-use GitHub App, push this project to that repository, and use `npx mcp-use deploy -y` instead.

See the [mcp-use v2 documentation](https://docs.mcp-use.com/v2/typescript/getting-started/welcome) for extending the app.
