import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

/**
 * Model output rendered as Markdown. react-markdown never renders raw HTML, so a
 * model can't inject markup; links open in a new tab and carry no SEO weight.
 */
export function Markdown({ children }: { children: string }) {
  return (
    <div className="space-y-3 text-[15px] leading-relaxed break-words">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: (p) => <h3 className="font-display text-lg font-bold" {...p} />,
          h2: (p) => <h3 className="font-display text-lg font-bold" {...p} />,
          h3: (p) => <h4 className="font-semibold" {...p} />,
          ul: (p) => <ul className="list-[square] space-y-1 pl-5 marker:text-tomato" {...p} />,
          ol: (p) => <ol className="list-decimal space-y-1 pl-5" {...p} />,
          a: ({ href, ...p }) => (
            <a href={href} target="_blank" rel="noopener nofollow ugc" className="underline decoration-tomato underline-offset-2" {...p} />
          ),
          pre: (p) => <pre className="overflow-x-auto border-2 border-ink bg-[#141311] p-3 font-mono text-[13px] text-[#e9e3d6]" {...p} />,
          code: ({ className, ...p }) =>
            className ? <code className={className} {...p} /> : <code className="bg-hairline px-1 font-mono text-[13px]" {...p} />,
          table: (p) => (
            <div className="overflow-x-auto">
              <table className="w-full border-collapse text-sm [&_td]:border [&_td]:border-hairline [&_td]:p-1.5 [&_th]:border [&_th]:border-ink [&_th]:p-1.5" {...p} />
            </div>
          ),
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
