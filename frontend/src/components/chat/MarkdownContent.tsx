import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Props {
 content: string;
 className?: string;
}

export default function MarkdownContent({ content, className }: Props) {
 return (
 <div className={`prose prose-sm max-w-none ${className || ""}`}>
 <ReactMarkdown
 remarkPlugins={[remarkGfm]}
 components={{
 h1: ({ children }) => <h1 className="text-base font-bold mt-3 mb-1">{children}</h1>,
 h2: ({ children }) => <h2 className="text-sm font-bold mt-2.5 mb-1">{children}</h2>,
 h3: ({ children }) => <h3 className="text-sm font-semibold mt-2 mb-1">{children}</h3>,
 p: ({ children }) => <p className="mb-1.5 leading-relaxed">{children}</p>,
 strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
 ul: ({ children }) => <ul className="list-disc pl-4 space-y-0.5 mb-1.5">{children}</ul>,
 ol: ({ children }) => <ol className="list-decimal pl-4 space-y-0.5 mb-1.5">{children}</ol>,
 li: ({ children }) => <li className="leading-relaxed">{children}</li>,
 code: ({ className: codeClassName, children, ...props }) => {
 const isBlock = codeClassName?.includes("language-");
 if (isBlock) {
 return (
 <pre className="bg-slate-100 p-3 rounded-lg text-xs overflow-auto mb-2">
 <code className={codeClassName}>{children}</code>
 </pre>
 );
 }
 return (
 <code
 className="bg-muted px-1 py-0.5 rounded text-xs" {...props}
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
 className="text-indigo-600 underline" target="_blank" rel="noopener noreferrer" >
 {children}
 </a>
 );
 },
 blockquote: ({ children }) => (
 <blockquote className="border-l-2 border-indigo-300 pl-3 italic text-slate-600 mb-1.5">
 {children}
 </blockquote>
 ),
 table: ({ children }) => (
 <div className="overflow-auto mb-2">
 <table className="min-w-full text-xs border-collapse border border-default">
 {children}
 </table>
 </div>
 ),
 th: ({ children }) => (
 <th className="border border-default px-2 py-1 bg-subtle font-semibold text-left">
 {children}
 </th>
 ),
 td: ({ children }) => (
 <td className="border border-default px-2 py-1">
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
