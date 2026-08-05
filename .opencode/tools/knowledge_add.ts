import { tool } from "@opencode-ai/plugin/tool";

const { schema: z } = tool;

export default tool({
  description: "Add a file to the knowledge garden through the MCP-backed CLI",
  args: {
    file: z.string(),
    tags: z.array(z.string()).optional(),
  },
  async execute(args: { file: string; tags?: string[] }) {
    const argv: string[] = ["kg-mcp", "add", args.file];
    for (const tag of args.tags ?? []) argv.push("--tag", tag);
    const proc = Bun.spawn(argv, { stdout: "pipe", stderr: "pipe" });
    const stdout = await new Response(proc.stdout).text();
    const stderr = await new Response(proc.stderr).text();
    const exitCode = await proc.exited;
    if (exitCode !== 0) {
      return { title: "kg-mcp add failed", output: stderr || stdout, metadata: { exitCode } };
    }
    return { title: "kg-mcp add", output: stdout };
  },
});