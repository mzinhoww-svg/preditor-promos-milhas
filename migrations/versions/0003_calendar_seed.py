"""seed calendar_event (idempotente)"""
from pathlib import Path

from alembic import op

revision = "0003"
# Compativel com a main atual (sem 0002) e com o PR #19 (com 0002) quando mesclado.
if (Path(__file__).resolve().parent / "0002_observed_at.py").is_file():
    down_revision = "0002"
else:
    down_revision = "0001"

UP = """
INSERT INTO calendar_event(name, kind, event_date)
SELECT v.name, v.kind, v.d::date
FROM (VALUES
  ('black_friday','retail','2024-11-29'),('black_friday','retail','2025-11-28'),('black_friday','retail','2026-11-27'),
  ('cyber_monday','retail','2024-12-02'),('cyber_monday','retail','2025-12-01'),('cyber_monday','retail','2026-11-30'),
  ('natal','retail','2024-12-25'),('natal','retail','2025-12-25'),('natal','retail','2026-12-25'),
  ('ano_novo','retail','2025-01-01'),('ano_novo','retail','2026-01-01')
) AS v(name, kind, d)
ON CONFLICT (name, event_date) DO NOTHING;
"""

DOWN = "DELETE FROM calendar_event WHERE name IN ('black_friday','cyber_monday','natal','ano_novo');"


def upgrade():
    op.execute(UP)


def downgrade():
    op.execute(DOWN)
