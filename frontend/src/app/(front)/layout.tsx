import { FullMasthead, PageMain } from "@/components/Header";

export default function FrontLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <FullMasthead />
      <PageMain>{children}</PageMain>
    </>
  );
}
