-- Idea Laval v2 is the only supported Ideas subsystem. Remove all legacy
-- C01-C10 / Idea Evolution runtime state so synthetic history cannot surface
-- as owner-created ideas. Laval tables and the active mission are preserved.
TRUNCATE TABLE
    telegram_inbox,
    telegram_offsets,
    telegram_events,
    reports,
    executions,
    idea_evaluations,
    ideas,
    idea_submission_drafts,
    idea_submissions,
    generations,
    guidance,
    context_revisions,
    contexts
RESTART IDENTITY CASCADE;

DELETE FROM missions AS candidate
WHERE candidate.is_active = FALSE
  AND NOT EXISTS (
      SELECT 1 FROM laval_runs WHERE laval_runs.mission_id = candidate.id
  );
