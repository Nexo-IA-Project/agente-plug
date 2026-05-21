// apps/web/src/app/(admin)/layout.tsx
import { Sidebar } from "@/shared/components/layout/Sidebar";
import { TopBar } from "@/shared/components/layout/TopBar";

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <div className="ml-[240px] flex flex-1 flex-col">
        <TopBar />
        <main className="flex-1 p-gutter">{children}</main>
      </div>
    </div>
  );
}
