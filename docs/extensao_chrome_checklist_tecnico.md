# Checklist técnico — Extensão Chrome MinhaOferta

## Antes de implementar

- [ ] Confirmar fluxo desejado da extensão.
- [ ] Confirmar se o primeiro MVP terá banner automático.
- [ ] Confirmar se o popup também será criado.
- [ ] Confirmar percentual padrão inicial de cashback.
- [ ] Confirmar se login será por sessão/cookie atual.
- [ ] Confirmar URLs finais do ambiente de produção.
- [ ] Confirmar se a extensão será publicada como não listada ou pública.

## Backend

- [ ] Criar endpoints específicos para extensão.
- [ ] Reaproveitar validação de URL existente.
- [ ] Reaproveitar criação de job existente.
- [ ] Garantir autenticação obrigatória para gerar link.
- [ ] Garantir isolamento por usuário.
- [ ] Adicionar origem/source nos jobs, se necessário.
- [ ] Não aceitar cashback enviado pela extensão como verdade.
- [ ] Adicionar rate limit.
- [ ] Revisar CSRF.
- [ ] Revisar CORS.
- [ ] Revisar cookies.
- [ ] Adicionar logs de auditoria.

## Extensão

- [ ] Criar manifest.json em Manifest V3.
- [ ] Criar popup.html.
- [ ] Criar popup.js.
- [ ] Criar content.js.
- [ ] Criar styles.css.
- [ ] Criar ícones.
- [ ] Capturar URL da aba atual.
- [ ] Validar Mercado Livre.
- [ ] Detectar página de produto.
- [ ] Mostrar aviso automático.
- [ ] Permitir fechar aviso.
- [ ] Não gerar job automaticamente.
- [ ] Gerar job somente após clique.
- [ ] Exibir status de carregamento.
- [ ] Exibir link gerado.
- [ ] Permitir copiar link.
- [ ] Abrir login em nova aba.
- [ ] Abrir histórico em nova aba.

## Segurança

- [ ] Não armazenar senha na extensão.
- [ ] Não expor token do worker.
- [ ] Não expor credenciais no código da extensão.
- [ ] Não permitir acesso a endpoints admin.
- [ ] Validar domínio no backend.
- [ ] Proteger contra subdomain spoofing.
- [ ] Garantir que usuário só veja seus próprios jobs.
- [ ] Bloquear abuso de criação de jobs.
- [ ] Registrar origem dos jobs.
- [ ] Revisar permissões mínimas no manifest.

## UX/UI

- [ ] Banner discreto.
- [ ] Não cobrir botão de compra.
- [ ] Não cobrir preço.
- [ ] Mensagem clara e confiável.
- [ ] Botão com CTA simples.
- [ ] Estados de erro claros.
- [ ] Estado de login claro.
- [ ] Estado de carregamento claro.
- [ ] Resultado fácil de copiar.
- [ ] Visual alinhado à identidade MinhaOferta.

## Publicação

- [ ] Preparar ZIP da extensão.
- [ ] Criar ícones finais.
- [ ] Criar screenshots.
- [ ] Criar descrição curta.
- [ ] Criar descrição completa.
- [ ] Criar política de privacidade.
- [ ] Justificar permissões.
- [ ] Definir distribuição pública ou não listada.
- [ ] Enviar para revisão na Chrome Web Store.
