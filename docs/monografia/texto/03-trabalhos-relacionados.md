# TRABALHOS RELACIONADOS

A detecção de acessos anômalos a bancos de dados relacionais é estudada há quase duas décadas, com abordagens que diferem na fonte de dados, na unidade analisada e na referência do que é normal. Este capítulo apresenta os trabalhos mais próximos e posiciona o SACLA em relação a eles.

## PERFIS POR PAPEL A PARTIR DA SINTAXE DAS CONSULTAS

Kamra, Terzi e Bertino (2008) propuseram um dos primeiros métodos de detecção de intrusão voltados ao SGBD. O método minera as consultas SQL registradas no log de auditoria do banco para construir perfis de acesso normal. Os autores consideram dois cenários. Quando o banco usa controle de acesso baseado em papéis, cada papel tem um perfil, e um classificador aponta o usuário cujas consultas não se parecem com as do seu papel. Sem papéis, as consultas são agrupadas, e os grupos fazem o papel dos perfis, com detecção de pontos fora deles. A avaliação usou registros reais e sintéticos de acesso.

Shebaro *et al.* (2013) levaram essa ideia para dentro do PostgreSQL. O detector extrai atributos da árvore sintática de cada comando e usa os papéis do SGBD como classes de um classificador bayesiano. No momento da detecção, o classificador estima o papel mais provável para o comando; se ele difere do papel de quem o executou, o sistema emite um alarme. A demonstração também mede o custo do treino e da detecção no desempenho do banco.

Ronao e Cho (2016) seguem a mesma formulação, também em bancos administrados por papéis, e usam floresta aleatória com análise de componentes principais para detectar consultas anômalas.

Essas abordagens têm em comum a pergunta que fazem: "esta consulta parece com as do papel de quem a executou?". Elas exigem papéis bem definidos e detectam quem se comporta como outro papel. Não captam, por exemplo, um atendente que faz consultas típicas de atendente, mas em volume, horário ou origem fora do seu costume.

## PERFIS A PARTIR DOS DADOS ACESSADOS

Mathew *et al.* (2010) partem da premissa de que a sintaxe da consulta, sozinha, é um sinal fraco da intenção do usuário. Os autores propõem uma abordagem centrada nos dados, que modela o padrão de acesso de cada usuário pelos dados que as suas consultas efetivamente acessam, e avaliam algoritmos de aprendizado estatístico em uma base real de admissões de pós-graduação.

Essa preocupação com o que foi lido, e não só com o que foi pedido, também está no SACLA, que usa a contagem de linhas retornadas e afetadas por comando, obtida do plano de execução registrado pelo `auto_explain`, e as tabelas efetivamente acessadas.

## SISTEMAS COMPLETOS DE DETECÇÃO E RESPOSTA

Sallam *et al.* (2017) apresentam o DBSAFE, um sistema para SGBDs relacionais que detecta acessos anômalos, emite alertas e responde a eles. O sistema constrói e mantém automaticamente perfis do comportamento normal de usuários e aplicações a partir de uma fase de treino e, quando detecta uma anomalia, aplica políticas predefinidas de resposta, automáticas ou humanas. A arquitetura não depende de um SGBD específico, e a avaliação relatada indica que as técnicas foram eficazes para detectar anomalias.

O DBSAFE inclui resposta automática, que está fora do escopo deste trabalho: o SACLA apenas aponta e explica comportamentos atípicos, e a decisão cabe a uma pessoa.

## AVALIAÇÃO DE DETECTORES DE ANOMALIA

Dois trabalhos fora da área de bancos de dados influenciaram o desenho da avaliação. Goldstein e Uchida (2016) compararam 19 algoritmos não supervisionados em 10 conjuntos de dados públicos, documentando desempenho, custo e sensibilidade a parâmetros. Comparações como essa reforçam a importância de avaliar um detector em mais de um conjunto de dados, princípio que este trabalho segue com várias simulações independentes. Sommer e Paxson (2010) apontam que poucas propostas de aprendizado de máquina para detecção de intrusão chegam ao uso real e recomendam que a avaliação explique o que o detector encontra e por quê, reconhecendo as limitações dos dados usados.

## POSICIONAMENTO DESTE TRABALHO

A @tab:trabalhos resume as diferenças entre o SACLA e os trabalhos discutidos.

Tabela: Comparação entre este trabalho e os trabalhos relacionados {#tab:trabalhos}

| Trabalho | Fonte de dados | Unidade analisada | Aprendizado | Referência de normalidade |
|---|---|---|---|---|
| Kamra, Terzi e Bertino (2008) | log de auditoria das consultas | consulta | classificação (com papéis) ou agrupamento (sem papéis) | papel ou grupo |
| Mathew *et al.* (2010) | dados acessados pelas consultas | consulta | aprendizado estatístico | perfil de acesso aos dados |
| Shebaro *et al.* (2013) | árvore sintática, dentro do PostgreSQL | consulta | classificador bayesiano | papel |
| Ronao e Cho (2016) | consultas em banco com papéis | consulta | floresta aleatória e PCA | papel |
| Sallam *et al.* (2017) | perfis de usuários e aplicações | consulta | perfis aprendidos em treino | usuário ou aplicação |
| Este trabalho | log nativo do PostgreSQL (jsonlog e auto_explain) | janela de 5 minutos por usuário | Isolation Forest, não supervisionado | histórico do próprio usuário |

Fonte: elaborada pelo autor (2026).

O SACLA se diferencia em quatro pontos:

- **Fonte de dados.** Usa só o log nativo do servidor, sem modificar o SGBD, sem extensões de auditoria e sem acesso às aplicações. A instrumentação se resume a parâmetros de configuração e ao módulo `auto_explain`, distribuído com o PostgreSQL.
- **Unidade e referência.** Em vez de classificar cada consulta por papel, agrega a atividade de cada usuário em janelas de cinco minutos e compara cada janela com o histórico do próprio usuário. Isso capta mudanças de volume, horário, origem, erros e falhas de autenticação, que não aparecem na sintaxe de uma consulta isolada.
- **Explicação.** Cada alerta vem acompanhado dos atributos mais raros para aquele usuário, em linguagem direta, e alertas seguidos são agrupados em episódios.
- **Avaliação.** O laboratório é reprodutível por comando, os rótulos ficam fora do log e a avaliação inclui linha de base explícita, réplicas, validação confirmatória com hipóteses registradas antes dos dados e um cenário com mudanças legítimas de rotina.
