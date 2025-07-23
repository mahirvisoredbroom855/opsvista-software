
/* Enabling Row‑Level Security ───────────────── */
ALTER TABLE public.tasks ENABLE ROW LEVEL SECURITY;

/*  Policy 1 — INSERT (owner/admin/manager only) ────── */
CREATE POLICY task_insert_by_roles
ON public.tasks
FOR INSERT
TO authenticated
WITH CHECK ( auth.role() IN ('owner','admin','manager') );


/*  Policy 2 — SELECT (self OR privileged roles) ────── */
CREATE POLICY task_select
ON public.tasks
FOR SELECT
TO authenticated
USING (
  assignee_id = auth.uid()
  OR auth.role() IN ('owner','admin','manager')
);

/*  Policy 3 — UPDATE status by assignee ────────────── */
CREATE POLICY task_update_status
ON public.tasks
FOR UPDATE
TO authenticated
USING ( assignee_id = auth.uid() )
WITH CHECK ( status IN ('in_progress','done','overdue') );

/* Policy 4 — UPDATE anything by owner/admin/manager ─ */
CREATE POLICY task_update_privileged
ON public.tasks
FOR UPDATE
TO authenticated
USING ( auth.role() IN ('owner','admin','manager') );
