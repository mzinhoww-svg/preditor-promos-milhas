# preditor-promos-milhas

Prevê as próximas promoções de pontos e milhas (PoC Livelo → Smiles, bônus de transferência).

```
cp .env.example .env   # ajuste as senhas locais
docker compose up -d --wait
export $(grep -v '^#' .env | xargs)
uv sync --python 3.12
uv run alembic upgrade head
uv run pytest
```
Veja `STATUS.md`, `TASKS.md` e `docs/`.
