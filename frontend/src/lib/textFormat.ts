const ACRONYMS = new Set([
  "ai",
  "api",
  "ci",
  "cd",
  "cli",
  "cors",
  "cpu",
  "css",
  "db",
  "dns",
  "e2e",
  "fk",
  "gpu",
  "html",
  "http",
  "https",
  "id",
  "io",
  "ip",
  "js",
  "json",
  "jwt",
  "llm",
  "ml",
  "nlp",
  "oauth",
  "orm",
  "os",
  "pdf",
  "pr",
  "qa",
  "rag",
  "rbac",
  "rest",
  "sdk",
  "seo",
  "sql",
  "ssl",
  "ssr",
  "tls",
  "ts",
  "tsx",
  "ui",
  "ux",
  "url",
  "uuid",
  "vpc",
  "xml",
  "yaml",
]);

const CONVENTIONAL_PREFIXES = [
  "feat",
  "fix",
  "refactor",
  "docs",
  "test",
  "chore",
  "perf",
  "ci",
  "build",
  "style",
  "revert",
  "merge",
  "hotfix",
  "wip",
];

const PREFIX_RE = new RegExp(
  `^\\s*(?:${CONVENTIONAL_PREFIXES.join("|")})(?:\\([^)]*\\))?!?\\s*[:：]\\s*`,
  "i",
);

const CO_AUTHORED_RE = /\s*(?:co-authored-by|signed-off-by|fixes|closes|resolves)\s*[:-]?.*$/gi;
const URL_RE = /https?:\/\/\S+/g;
const ISSUE_REF_RE = /#\d+/g;
const MARKDOWN_RE = /[*`>#]+/g;
const MULTI_WS_RE = /\s+/g;

function titleWord(word: string): string {
  if (!word) return word;
  const lower = word.toLowerCase();
  if (ACRONYMS.has(lower)) return lower.toUpperCase();
  if (/\d/.test(lower) && lower.length <= 4) return lower.toUpperCase();
  return lower.charAt(0).toUpperCase() + lower.slice(1);
}

function titleCase(text: string): string {
  return text
    .split(/(\s+|[-/])/)
    .map((part) => {
      if (/^\s+$/.test(part) || part === "-" || part === "/") return part;
      return titleWord(part);
    })
    .join("");
}

function stripNoise(raw: string): string {
  if (!raw) return "";
  let text = String(raw);
  text = text.replace(URL_RE, "");
  text = text.replace(CO_AUTHORED_RE, "");
  text = text.replace(MARKDOWN_RE, "");
  text = text.replace(ISSUE_REF_RE, "");
  text = text.split(/\r?\n/)[0];
  text = text.replace(MULTI_WS_RE, " ").trim();
  text = text.replace(/^[:：\-—–•·,;\s]+/, "");
  text = text.replace(/[:：\-—–•·,;\s]+$/, "");
  return text;
}

function stripPrefix(text: string): string {
  let out = text;
  for (let i = 0; i < 3; i += 1) {
    const next = out.replace(PREFIX_RE, "");
    if (next === out) break;
    out = next;
  }
  return out.replace(/^[:：\-—–•·,;\s]+/, "").trim();
}

export function cleanTopicLabel(raw: string | null | undefined, maxLen = 36): string {
  if (!raw) return "";
  const original = String(raw).trim();
  let text = stripNoise(raw);
  text = stripPrefix(text);
  if (!text) return "";

  const untouched = text === original;
  const hasUppercase = /[A-Z]/.test(text);

  if (text.length > maxLen) {
    const truncated = text.slice(0, maxLen - 1);
    const lastSpace = truncated.lastIndexOf(" ");
    text = (lastSpace > maxLen * 0.6 ? truncated.slice(0, lastSpace) : truncated).trimEnd() + "…";
  }

  if (untouched && hasUppercase) return text;
  return titleCase(text);
}

export function cleanDescription(raw: string | null | undefined, maxLen = 140): string {
  if (!raw) return "";
  let text = stripNoise(raw);
  text = stripPrefix(text);
  if (!text) return "";

  if (text.length > maxLen) {
    const truncated = text.slice(0, maxLen - 1);
    const lastSpace = truncated.lastIndexOf(" ");
    text = (lastSpace > maxLen * 0.7 ? truncated.slice(0, lastSpace) : truncated).trimEnd() + "…";
  }

  return text.charAt(0).toUpperCase() + text.slice(1);
}

export function cleanTopicWithTooltip(raw: string | null | undefined, maxLen = 36): {
  label: string;
  title: string;
} {
  const label = cleanTopicLabel(raw, maxLen);
  const title = (raw || "").toString().replace(MULTI_WS_RE, " ").trim();
  return { label, title: title !== label ? title : "" };
}
