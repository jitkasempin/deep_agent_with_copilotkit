import { MCPServer } from "mcp-use";
import { z } from "zod";

const server = new MCPServer({
  name: "mcp-app",
  title: "MCP Widget Playground", // Human readable name of the server
  version: "1.0.0",
  description: "An interactive MCP Apps demo with a counter and greeting tool.",
  instructions: "Use show-app to open the interactive widget playground. Use say-hello to greet someone by name.",
  websiteUrl: "https://mcp-use.com",
  // Icons for your MCP Server, from public/ (or absolute URLs).
  icons: [
    {
      src: "icon.svg",
      mimeType: "image/svg+xml",
      sizes: ["512x512"],
    },
  ],

  // The MCP server is by default served at /mcp, to customise
  // basePath: "/mcp",

  // mcp-use has 1 line adapter for OAuth, import from mcp-use/oauth/*
  // oauth: oauthClerkProvider(), // zero-config via MCP_USE_OAUTH_CLERK_FRONTEND_API_URL, import from mcp-use/oauth/*

  // When OAuth is on, the HTML landing page (/mcp) is protected by default, set to true to keep the landing page public while /mcp stays bearer-protected.
  // publicLandingPage: true,
});

// TOOLS

// tool inputs are zod schemas. Important: set decriptions for the model to understand the input.
const showAppInputSchema = z.object({
  appName: z
    .string()
    .optional()
    .describe(
      "Optional title shown in the MCP App card instead of the default"
    ),
});

// tool outputs are zod schemas. Important: set descriptions for the model to understand the output.
const showAppOutputSchema = z.object({
  message: z.string().describe("Message to display in the MCP App"),
});

export const showApp = server.tool(
  {
    name: "show-app", // Unique tool id on the wire.
    title: "Show MCP App", // Short label in inspector and client UIs (falls back to name).
    description: "Open an interactive widget with a counter, greeting button, and host controls.",
    inputSchema: showAppInputSchema, // Validated before the handler runs; .describe() text becomes LLM hints.
    outputSchema: showAppOutputSchema, // Required when binding a view — the view reads structuredContent typed by this.
    view: {
      name: "my-view", // directory under views/
      description: "MCP App starter card with interactive demo hooks",
      prefersBorder: false, // ask the host to skip a card border around the view
      csp: {
        resourceDomains: [
          "https://fonts.googleapis.com",
          "https://fonts.gstatic.com",
        ],
      },
    },
    // Behavioral hints for clients (readOnly / destructive / open-world).
    annotations: {
      readOnlyHint: true,
      destructiveHint: false,
      openWorldHint: false,
    },
  },
  async ({ appName }) => {
    // Brief delay so the pending skeleton is visible during dev/inspector demos.
    await new Promise((resolve) => setTimeout(resolve, 1500));

    const title = appName?.trim() || "MCP Widget Playground";
    const data = { message: `${title} is ready. Try the counter, call the greeting tool, or send a follow-up message.` };

    return {
      content: [{ type: "text", text: data.message }],
      structuredContent: data,
    };
  }
);

// say-hello — plain tool (no view); used by the Say Hello button in my-view
const sayHelloInputSchema = z.object({
  name: z.string().describe("Name to greet"),
});

const sayHelloOutputSchema = z.object({
  greeting: z.string().describe("Greeting to display"),
});

export const sayHello = server.tool(
  {
    name: "say-hello",
    title: "Say hello",
    description: "Returns a greeting for the Say Hello button demo",
    inputSchema: sayHelloInputSchema,
    outputSchema: sayHelloOutputSchema,
    annotations: {
      readOnlyHint: true,
      destructiveHint: false,
      openWorldHint: false,
    },
  },
  async ({ name }) => {
    const data = { greeting: `Hello, ${name}!` };
    return {
      content: [{ type: "text", text: data.greeting }],
      structuredContent: data,
    };
  }
);

export default server;
