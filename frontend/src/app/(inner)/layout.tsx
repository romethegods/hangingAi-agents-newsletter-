import { PageMain, SlimHeader } from "@/components/Header";

export default function InnerLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <SlimHeader />
      <PageMain>{children}</PageMain>
    </>
  );
}
