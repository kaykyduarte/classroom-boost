(() => {
  const pagina = document.querySelector('[data-chat]');
  if (!pagina || !window.fetch) return;

  const historico = pagina.querySelector('[data-chat-historico]');
  const form = pagina.querySelector('[data-chat-form]');
  const campo = form.elements.conteudo;
  const enviar = form.querySelector('button[type="submit"]');
  const atualizar = pagina.querySelector('[data-atualizar-historico]');
  const feedback = pagina.querySelector('[data-chat-feedback]');
  const formatoData = new Intl.DateTimeFormat('pt-BR', {
    dateStyle: 'short', timeStyle: 'short', timeZone: 'America/Sao_Paulo',
  });
  let ocupado = false;
  atualizar.hidden = false;

  const mostrarFeedback = (texto) => {
    feedback.textContent = texto;
    feedback.hidden = !texto;
  };

  const definirOcupado = (valor) => {
    ocupado = valor;
    enviar.disabled = valor;
    atualizar.disabled = valor;
    form.setAttribute('aria-busy', String(valor));
  };

  const requisitarJson = async (url, options = {}) => {
    const resposta = await fetch(url, {
      ...options,
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    });
    if (resposta.redirected) throw new Error('Sua sessão expirou. Entre novamente para continuar.');
    if (resposta.status === 403) throw new Error('Você não tem permissão para esta ação. Atualize a página.');
    if (resposta.status === 404) throw new Error('Esta conversa não está disponível.');
    if (resposta.status === 400) {
      const dados = await resposta.json();
      throw new Error(dados.erro || 'Confira o conteúdo da mensagem.');
    }
    if (!resposta.ok) throw new Error('Não foi possível concluir a ação. Tente novamente.');
    return resposta.json();
  };

  const criarMensagem = (mensagem) => {
    const minha = String(mensagem.remetente_id) === pagina.dataset.usuarioId;
    const artigo = document.createElement('article');
    artigo.className = `chat-message ${minha ? 'chat-message-mine' : 'chat-message-theirs'}`;
    artigo.dataset.mensagemId = mensagem.id;

    const meta = document.createElement('div');
    meta.className = 'chat-message-meta';
    const nome = document.createElement('strong');
    nome.textContent = minha ? 'Você' : pagina.dataset.outroNome;
    const data = document.createElement('time');
    data.dateTime = mensagem.enviada_em;
    data.textContent = formatoData.format(new Date(mensagem.enviada_em));
    meta.append(nome, data);

    const texto = document.createElement('div');
    texto.className = 'chat-message-bubble';
    texto.textContent = mensagem.conteudo;
    artigo.append(meta, texto);
    return artigo;
  };

  const mostrarErro = (erro) => {
    mostrarFeedback(erro instanceof TypeError
      ? 'Não foi possível conectar ao servidor. Verifique sua conexão e tente novamente.'
      : erro.message);
  };

  atualizar.addEventListener('click', async () => {
    if (ocupado) return;
    definirOcupado(true);
    mostrarFeedback('');
    try {
      const dados = await requisitarJson(pagina.dataset.historicoUrl);
      if (!Array.isArray(dados.mensagens)) throw new Error('Não foi possível carregar o histórico.');
      const fragmento = document.createDocumentFragment();
      for (const mensagem of dados.mensagens) fragmento.append(criarMensagem(mensagem));
      if (!dados.mensagens.length) {
        const vazio = document.createElement('div');
        vazio.className = 'chat-empty-state';
        vazio.dataset.chatVazio = '';
        vazio.textContent = 'Nenhuma mensagem enviada ainda. Comece a conversa.';
        fragmento.append(vazio);
      }
      historico.replaceChildren(fragmento);
      historico.scrollTop = historico.scrollHeight;
      mostrarFeedback('Histórico atualizado.');
    } catch (erro) {
      mostrarErro(erro);
    } finally {
      definirOcupado(false);
    }
  });

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (ocupado) return;
    if (!campo.value.trim()) {
      mostrarFeedback('O conteúdo da mensagem não pode estar vazio.');
      campo.focus();
      return;
    }

    const textoEnviado = campo.value;
    const dadosForm = new FormData(form);
    definirOcupado(true);
    mostrarFeedback('Enviando mensagem…');
    try {
      const mensagem = await requisitarJson(form.action, { method: 'POST', body: dadosForm });
      if (!Number.isInteger(mensagem.id)) throw new Error('Não foi possível confirmar o envio. Atualize as mensagens antes de tentar novamente.');
      historico.querySelector('[data-chat-vazio]')?.remove();
      if (!historico.querySelector(`[data-mensagem-id="${mensagem.id}"]`)) {
        historico.append(criarMensagem(mensagem));
      }
      if (campo.value === textoEnviado) campo.value = '';
      historico.scrollTop = historico.scrollHeight;
      mostrarFeedback('Mensagem enviada.');
      campo.focus();
    } catch (erro) {
      mostrarErro(erro);
    } finally {
      definirOcupado(false);
    }
  });

  historico.scrollTop = historico.scrollHeight;
})();
