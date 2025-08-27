'use client';

import AuthGate from "@/components/AuthGate";
import Chat from "@/components/Chat";
import FinanceSummary from "@/components/FinanceSummary";
import Tasks from "@/components/Tasks";

export default function Page() {
  return (
    <AuthGate>
      <main className="space-y-6">
        <section className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2">
            <div className="rounded-2xl border bg-white p-4 shadow-sm">
              <h2 className="mb-2 text-lg font-medium">RAG Chat</h2>
              <Chat />
            </div>
          </div>
          <div className="rounded-2xl border bg-white p-4 shadow-sm">
            <h2 className="mb-2 text-lg font-medium">Finance Summary</h2>
            <FinanceSummary />
          </div>
        </section>

        <section className="rounded-2xl border bg-white p-4 shadow-sm">
          <h2 className="mb-2 text-lg font-medium">Tasks</h2>
          <Tasks />
        </section>
      </main>
    </AuthGate>
  );
}
