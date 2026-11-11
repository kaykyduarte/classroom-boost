# Revisão manual da interface

Inicie o servidor na raiz do projeto:

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

Abra `http://127.0.0.1:8000/`. Use navegadores ou perfis separados para manter as sessões de professor e aluno.

## Preparar as contas

1. Cadastre um aluno pela opção **Criar conta** e entre com as credenciais escolhidas.
2. Para a conta de professor, use o admin em `/admin/`: crie um usuário com o tipo **PROFESSOR** e uma senha. Ser professor não exige acesso ao admin.
3. Se ainda não houver um administrador, execute `python manage.py createsuperuser` no ambiente virtual e use essa conta para acessar o admin.
4. Entre com a conta de professor pela tela `/conta/entrar/`.

## Turma, atividade e XP

1. Como professor, abra **Disciplinas → Criar turma** e selecione o aluno cadastrado.
2. Abra a turma e escolha **Nova atividade**. Defina um prazo entre 24 e 48 horas no futuro, no horário de São Paulo.
3. Como aluno, confira se a turma e a atividade aparecem no painel e nas listagens.
4. Abra **Notificações** e marque o aviso como lido. O estado e o contador devem ser atualizados.
5. Volte ao painel e ao ranking: o aluno deve ter recebido 10 XP. Recarregar as páginas não deve conceder XP adicional.

Notificações NORMAL não concedem XP; IMPORTANTE e URGENTE concedem 10 XP uma única vez por notificação. O ranking mostra até 20 alunos ativos.

## Chat

1. Na turma, como aluno, escolha **Conversar com o professor** e envie uma mensagem.
2. Como professor, abra **Mensagens**, acesse a conversa e responda.
3. Como aluno, clique em **Atualizar mensagens** para buscar a resposta. A atualização nesta etapa é manual.
4. Recarregue a página: o histórico deve continuar disponível e ordenado.
5. Abrir novamente a mesma conversa não deve criar uma conversa duplicada.

## Acesso e aparência

- Uma conta de aluno sem matrícula não deve acessar o detalhe da turma ou da atividade.
- Um usuário fora da conversa não deve ler nem enviar mensagens nela, mesmo tendo acesso ao admin.
- Confira os formulários inválidos, as listas vazias, os textos longos e as quebras de linha.
- Em uma janela estreita, confira o botão do menu lateral e se as páginas permitem leitura e uso dos formulários.
- Confira o envio e a atualização no navegador: os testes Django não executam o JavaScript.

Os históricos existentes do chat continuam disponíveis para seus participantes após a remoção da matrícula; iniciar uma conversa exige matrícula atual.

## Verificação automatizada

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test
```

O teste `usuarios.test_fluxo_integrado` percorre cadastro, login, matrícula, publicação, notificações, XP, ranking e chat usando o cliente HTTP do Django com CSRF habilitado. Os dados desses testes ficam no banco de testes.

As telas de entrega e correção do projeto temporário dependem de modelos e regras que ainda não foram implementados no projeto principal.
