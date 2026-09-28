import { Squiggle } from "./Geometry";

/** Section-front header: kicker, big display title, standfirst. */
export function PageHeader({
  kicker,
  title,
  children,
}: {
  kicker: string;
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <header className="mb-8 space-y-3">
      <p className="kicker text-tomato">{kicker}</p>
      <h1 className="font-display text-4xl leading-none font-black tracking-tight sm:text-5xl">
        {title}
      </h1>
      <Squiggle className="h-3 w-28 text-ink" />
      {children && <p className="max-w-2xl text-lg text-muted">{children}</p>}
    </header>
  );
}
