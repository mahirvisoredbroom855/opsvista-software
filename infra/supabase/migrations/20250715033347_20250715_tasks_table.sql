-- 1️⃣  Make sure UUID generation is available (local & cloud safe)
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 2️⃣  Create table
CREATE TABLE public.tasks (
  task_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title       TEXT NOT NULL,
  description TEXT,
  assigner_id UUID NOT NULL REFERENCES auth.users(id),
  assignee_id UUID NOT NULL REFERENCES auth.users(id),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  due_date    DATE NOT NULL,
  status      TEXT NOT NULL DEFAULT 'pending'
               CHECK (status IN ('pending','in_progress','done','overdue')),
  priority    TEXT NOT NULL DEFAULT 'medium'
               CHECK (priority IN ('low','medium','high','urgent')),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  done_at     TIMESTAMPTZ
);

-- 3️⃣  Add indexes (separate statements executed after table exists)
CREATE INDEX idx_tasks_assignee_status ON public.tasks (assignee_id, status);
CREATE INDEX idx_tasks_due_date        ON public.tasks (due_date);
CREATE INDEX idx_tasks_status          ON public.tasks (status);
