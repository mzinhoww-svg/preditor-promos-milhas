# 001 Escopo: sem Telegram e execução local primeiro

Data: 2026-10-13. Decisão de Aurimar.

- Telegram sai do MVP (login por SMS, listener e credenciais: complexidade que agora não compensa). O listener em tempo real passa a ser um coletor por polling de feed/RSS/HTML das fontes públicas.
- Tudo roda local (Docker Compose) até a base de dados e o modelo funcionarem; só então sobe na VPS.
- Repositório público; gitleaks no CI barra segredos.
- Teto de gasto: R$ 100 (OpenRouter); Vercel no plano gratuito; VPS existente em diretório próprio.
