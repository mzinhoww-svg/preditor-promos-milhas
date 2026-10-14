"""unicidade idempotente em prediction_log por dia logico"""
from alembic import op

revision = "0003"
down_revision = "0002"
UP = """
CREATE UNIQUE INDEX IF NOT EXISTS uq_prediction_log_logical
ON prediction_log (model_version, origin, destination, event_type, horizon_days,
                   ((logged_at AT TIME ZONE 'UTC')::date));
"""
DOWN = "DROP INDEX IF EXISTS uq_prediction_log_logical;\n"
def upgrade():
    op.execute(UP)
def downgrade():
    op.execute(DOWN)
