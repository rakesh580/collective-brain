import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Props {
 content: string;
 className?: string;
}

export default function MarkdownContent({ content, className }: Props) {
 return (
 <div className={`prose prose-sm max-w-none ${className || ""}`} style={{ color: "inherit" }}>
 <ReactMarkdown
 remarkPlugins={[remarkGfm]}
 components={{
 h1: ({ children }) => <h1 className="text-base font-bold mt-3 mb-1" style={{ color: "var(--text-primary)" }}>{children}</h1>,
 h2: ({ children }) => <h2 className="text-sm font-bold mt-2.5 mb-1" style={{ color: "var(--text-primary)" }}>{children}</h2>,
 h3: ({ children }) => <h3 className="text-sm font-semibold mt-2 mb-1" style={{ color: "var(--text-primary)" }}>{children}</h3>,
 p: ({ children }) => <p className="mb-1.5 leading-relaxed" style={{ color: "inherit" }}>{children}</p>,
 strong: ({ children }) => <strong className="font-semibold" style={{ color: "var(--text-primary)" }}>{children}</strong>,
 ul: ({ children }) => <ul className="list-disc pl-4 space-y-0.5 mb-1.5" style={{ color: "inherit" }}>{children}</ul>,
 ol: ({ children }) => <ol className="list-decimal pl-4 space-y-0.5 mb-1.5" style={{ color: "inherit" }}>{children}</ol>,
 li: ({ children }) => <li className="leading-relaxed" style={{ color: "inherit" }}>{children}</li>,
 code: ({ className: codeClassName, children, ...props }) => {
 const isBlock = codeClassName?.includes("language-");
 if (isBlock) {
 return (
 <pre className="p-3 rounded-lg text-xs overflow-auto mb-2" style={{ background: "var(--bg-muted)", color: "var(--text-primary)" }}>
 <code className={codeClassName}>{children}</code>
 </pre>
 );
 }
 return (
 <code
 className="px-1 py-0.5 rounded text-xs" style={{ background: "var(--bg-muted)", color: "var(--text-primary)" }} {...props}
 >
 {children}
 </code>
 );
 },
 pre: ({ children }) => <>{children}</>,
 a: ({ href, children }) => {
 const safeHref = href && (href.startsWith("http://") || href.startsWith("https://") || href.startsWith("mailto:")) ? href : undefined;
 return (
 <a
 href={safeHref}
 className="underline" style={{ color: "var(--brand-400)" }} target="_blank" rel="noopener noreferrer" >
 {children}
 </a>
 );
 },
 blockquote: ({ children }) => (
 <blockquote className="border-l-2 pl-3 italic mb-1.5" style={{ borderColor: "var(--brand-400)", color: "var(--text-secondary)" }}>
 {children}
 </blockquote>
 ),
 table: ({ children }) => (
 <div className="overflow-auto mb-2">
 <table className="min-w-full text-xs border-collapse" style={{ border: "1px solid var(--border-default)" }}>
 {children}
 </table>
 </div>
 ),
 th: ({ children }) => (
 <th className="px-2 py-1 font-semibold text-left" style={{ border: "1px solid var(--border-default)", background: "var(--bg-muted)", color: "var(--text-primary)" }}>
 {children}
 </th>
 ),
 td: ({ children }) => (
 <td className="px-2 py-1" style={{ border: "1px solid var(--border-default)", color: "var(--text-primary)" }}>
 {children}
 </td>
 ),
 }}
 >
 {content}
 </ReactMarkdown>
 </div>
 );
}
