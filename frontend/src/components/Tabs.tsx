import Link from "next/link";

export interface Tab {
  key: string;
  label: string;
  href: string;
}

/** Segmented control: ink-bordered blocks, the active one filled solid. */
export function Tabs({ tabs, active, label }: { tabs: Tab[]; active: string; label: string }) {
  return (
    <nav aria-label={label} className="overflow-x-auto">
      <ul className="inline-flex border-2 border-ink">
        {tabs.map((tab) => {
          const current = tab.key === active;
          return (
            <li key={tab.key} className="border-r-2 border-ink last:border-none">
              <Link
                href={tab.href}
                aria-current={current ? "page" : undefined}
                className={`kicker block px-3 py-2 font-semibold whitespace-nowrap ${
                  current ? "bg-ink text-paper" : "hover:bg-mustard hover:text-[#171614]"
                }`}
              >
                {tab.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
