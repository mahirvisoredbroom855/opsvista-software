'use client';

import { useEffect, useState } from 'react';
import { createClient } from '@/lib/supabaseClient';

type Summary = {
  id: number;
  summary_type: string;
  period_start: string;
  period_end: string;
  total_cash_received: number | null;
  total_expenses: number | null;
  net_cash_flow: number | null;
  total_bills_due: number | null;
  total_advances_paid: number | null;
  amounts_bdt: number | null;
  amounts_usd: number | null;
  total_revenue: number | null;
  total_expenditure: number | null;
  profit_loss: number | null;
};

export default function FinanceSummary() {
  const supabase = createClient();
  const [data, setData] = useState<Summary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      const { data, error } = await supabase
        .from('finance_summary')
        .select('*')
        .order('period_end', { ascending: false })
        .limit(1)
        .maybeSingle();
      if (error) setError(error.message);
      else setData(data);
    };
    load();
  }, [supabase]);

  if (error) return <div className="text-sm text-red-600">Error: {error}</div>;
  if (!data) return <div className="text-sm text-neutral-500">No summary yet.</div>;

  const Stat = ({ label, value }: { label: string, value: any }) => (
    <div className="rounded-xl border bg-white p-3 shadow-sm">
      <div className="text-xs text-neutral-500">{label}</div>
      <div className="text-lg font-semibold">{value ?? 0}</div>
    </div>
  );

  return (
    <div className="grid grid-cols-2 gap-3">
      <Stat label="Period" value={`${data.period_start} → ${data.period_end}`} />
      <Stat label="Net Cash Flow" value={data.net_cash_flow} />
      <Stat label="Cash Received" value={data.total_cash_received} />
      <Stat label="Expenses" value={data.total_expenses} />
      <Stat label="Bills Due" value={data.total_bills_due} />
      <Stat label="Advances Paid" value={data.total_advances_paid} />
      <Stat label="Revenue (Total)" value={data.total_revenue} />
      <Stat label="Expenditure (Total)" value={data.total_expenditure} />
      <Stat label="Profit/Loss" value={data.profit_loss} />
    </div>
  );
}
