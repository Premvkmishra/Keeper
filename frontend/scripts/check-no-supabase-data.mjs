import { readdir, readFile } from "node:fs/promises";
import path from "node:path";

const sourceRoot = path.resolve("src");
const forbidden =
  /\.from\s*\(\s*['"`]|\.rpc\s*\(|\.storage\b|\.channel\s*\(|service_role|SERVICE_ROLE/;
const violations = [];

async function scan(directory) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const filePath = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      await scan(filePath);
      continue;
    }
    if (!/\.(ts|tsx)$/.test(entry.name) || entry.name === "routeTree.gen.ts") continue;

    const contents = await readFile(filePath, "utf8");
    contents.split(/\r?\n/).forEach((line, index) => {
      if (forbidden.test(line)) {
        violations.push(`${path.relative(process.cwd(), filePath)}:${index + 1}: ${line.trim()}`);
      }
    });
  }
}

await scan(sourceRoot);
if (violations.length) {
  console.error("Forbidden Supabase business-data access found:");
  console.error(violations.join("\n"));
  process.exitCode = 1;
} else {
  console.log("OK: no Supabase business-data access in frontend source.");
}
