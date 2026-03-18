"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface MarkdownProps {
  content: string;
  className?: string;
}

export function Markdown({ content, className = "" }: MarkdownProps) {
  return (
    <div className={`prose prose-sm max-w-none dark:prose-invert ${className}`}>
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        h1: ({ children }) => (
          <h1 className="text-xl font-bold mt-4 mb-2 border-b border-[var(--border)] pb-2">
            {children}
          </h1>
        ),
        h2: ({ children }) => (
          <h2 className="text-lg font-semibold mt-3 mb-1.5">{children}</h2>
        ),
        h3: ({ children }) => (
          <h3 className="text-base font-semibold mt-2.5 mb-1">{children}</h3>
        ),
        p: ({ children }) => <p className="my-1.5 leading-relaxed">{children}</p>,
        ul: ({ children }) => (
          <ul className="my-1.5 ml-4 list-disc space-y-0.5">{children}</ul>
        ),
        ol: ({ children }) => (
          <ol className="my-1.5 ml-4 list-decimal space-y-0.5">{children}</ol>
        ),
        li: ({ children }) => <li className="leading-relaxed">{children}</li>,
        code: ({ className: codeClassName, children, ...props }) => {
          const isInline = !codeClassName;
          if (isInline) {
            return (
              <code className="rounded bg-[var(--secondary)] px-1.5 py-0.5 text-xs font-mono">
                {children}
              </code>
            );
          }
          return (
            <code
              className={`block overflow-x-auto rounded-lg bg-[var(--secondary)] p-3 text-xs font-mono leading-relaxed ${codeClassName || ""}`}
              {...props}
            >
              {children}
            </code>
          );
        },
        pre: ({ children }) => <pre className="my-2 overflow-x-auto">{children}</pre>,
        blockquote: ({ children }) => (
          <blockquote className="my-2 border-l-3 border-[var(--primary)] pl-3 italic text-[var(--muted-foreground)]">
            {children}
          </blockquote>
        ),
        table: ({ children }) => (
          <div className="my-2 overflow-x-auto">
            <table className="w-full border-collapse text-sm">{children}</table>
          </div>
        ),
        th: ({ children }) => (
          <th className="border border-[var(--border)] bg-[var(--secondary)] px-3 py-1.5 text-left font-semibold">
            {children}
          </th>
        ),
        td: ({ children }) => (
          <td className="border border-[var(--border)] px-3 py-1.5">{children}</td>
        ),
        a: ({ children, href }) => (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[var(--primary)] underline hover:opacity-80"
          >
            {children}
          </a>
        ),
        hr: () => <hr className="my-3 border-[var(--border)]" />,
        strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
      }}
    >
      {content}
    </ReactMarkdown>
    </div>
  );
}
