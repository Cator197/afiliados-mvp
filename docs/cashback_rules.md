# Regras de cashback estimado (Extensão)

A tabela `cashback_rules` controla o percentual **estimado** exibido no preview da extensão.

## Campos
- `platform`, `name`, `match_type`, `match_value`, `cashback_percent`, `priority`, `active`, `notes`, `created_at`, `updated_at`.

## match_type
- `default`: regra padrão da plataforma.
- `path_contains`: aplica quando a URL contém `match_value`.
- `category_hint_contains`: aplica quando `category_hint` contém `match_value`.

## Seleção da melhor regra
1. Busca regras ativas da plataforma por prioridade crescente.
2. Aplica a primeira regra específica compatível.
3. Se não houver, usa `default`.
4. Se não houver `default` no banco, usa fallback de configuração.

## Exemplo
- `mercadolivre / Celulares / path_contains=celulares / 5% / priority 10`
- `mercadolivre / Mercado Livre padrão / default / 3% / priority 100`

## Importante
Essas regras são usadas apenas no preview estimado da extensão. Não confirmam compra, não pagam cashback e não substituem validação administrativa.

## PR 9 — Extensão Chrome (UX e rastreabilidade)

Este PR melhora UX da extensão e rastreabilidade operacional (`source=extension`) sem alterar regras financeiras oficiais, cálculo/pagamento de cashback, worker ou metadata worker.
