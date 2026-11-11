(() => {
  const pagina = document.querySelector('[data-notificacoes]');
  if (!pagina || !window.fetch) return;

  const contador = pagina.querySelector('[data-contador-nao-lidas]');
  const feedback = pagina.querySelector('[data-notificacao-feedback]');

  pagina.addEventListener('submit', async (event) => {
    const form = event.target;
    if (!form.matches('[data-marcar-notificacao]')) return;
    event.preventDefault();
    if (form.dataset.enviando === 'true') return;

    const botao = form.querySelector('button[type="submit"]');
    form.dataset.enviando = 'true';
    botao.disabled = true;
    botao.textContent = 'Salvando…';
    feedback.hidden = true;

    try {
      const resposta = await fetch(form.action, {
        method: 'POST',
        headers: { Accept: 'application/json' },
        credentials: 'same-origin',
        body: new FormData(form),
      });

      if (resposta.redirected) {
        throw new Error('Sua sessão expirou. Entre novamente para continuar.');
      }
      if (resposta.status === 403) {
        throw new Error('Não foi possível autorizar a ação. Atualize a página e tente novamente.');
      }
      if (resposta.status === 404) {
        throw new Error('Esta notificação não está mais disponível. Atualize a página.');
      }
      if (!resposta.ok) {
        throw new Error('Não foi possível salvar. Tente novamente.');
      }

      const dados = await resposta.json();
      if (dados.success !== true) {
        throw new Error('Não foi possível confirmar a leitura. Atualize a página.');
      }

      const notificacao = form.closest('.notification-full');
      notificacao.classList.remove('unread');
      const estado = notificacao.querySelector('[data-estado-notificacao]');
      estado.textContent = 'Visualizada';
      estado.classList.remove('state-new');
      form.remove();
      contador.textContent = `${pagina.querySelectorAll('.notification-full.unread').length} não lida(s)`;
      feedback.textContent = 'Notificação marcada como lida.';
    } catch (erro) {
      feedback.textContent = erro instanceof TypeError
        ? 'Não foi possível conectar ao servidor. Verifique sua conexão e tente novamente.'
        : erro.message;
    } finally {
      feedback.hidden = false;
      delete form.dataset.enviando;
      botao.disabled = false;
      botao.textContent = 'Marcar como lida';
    }
  });
})();
