"""Метка уже применённой ревизии живой базы. Новых таблиц не создаёт."""

revision = "0024_analytics"
down_revision = "0023_process_description"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Таблицы этой ревизии уже есть в базе, которая была собрана раньше.
    # Повторно их не создаём: текущий код на них не опирается.
    pass


def downgrade() -> None:
    pass
