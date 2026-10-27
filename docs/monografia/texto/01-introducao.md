# INTRODUÇÃO

Os bancos de dados relacionais guardam o que as organizações têm de mais sensível: cadastros de clientes, pagamentos, contratos, dados de saúde. A segurança desses sistemas tradicionalmente se apoia no controle de acesso, que define quem pode ler ou alterar cada objeto (Bertino; Sandhu, 2005). O controle de acesso, porém, responde apenas se uma operação é permitida; ele não diz se uma operação permitida faz sentido para quem a executa naquele momento. Um atendente que pode consultar clientes não é barrado ao consultar milhares deles de madrugada, e um serviço com permissão de escrita não é impedido de alterar quinhentos registros de uma vez.

Esse limite importa porque uma parte relevante dos incidentes envolve pessoas ou credenciais legítimas. O guia de ameaças internas do CERT, construído a partir de mais de setecentos casos, descreve sabotagem, roubo de propriedade intelectual e fraude cometidos por funcionários e terceiros com acesso autorizado (Cappelli; Moore; Trzeciak, 2012). Uma credencial roubada produz o mesmo efeito: do ponto de vista do banco, quem age é o usuário legítimo. No Brasil, a Lei Geral de Proteção de Dados Pessoais exige dos agentes de tratamento "medidas de segurança, técnicas e administrativas aptas a proteger os dados pessoais de acessos não autorizados" (Brasil, 2018, art. 46), o que inclui perceber quando um acesso, ainda que autorizado pelo sistema, é indevido.

Uma forma de perceber esses acessos é observar o comportamento. Cada usuário de um banco de dados tem uma rotina: horários, volume de comandos, tabelas consultadas, origem das conexões. Um desvio forte dessa rotina não prova um ataque, mas é exatamente o tipo de sinal que merece a atenção de quem administra o sistema. Essa é a ideia da detecção de anomalias, uma área com longa tradição em segurança da informação (Chandola; Banerjee; Kumar, 2009) e já aplicada a bancos de dados relacionais (Kamra; Terzi; Bertino, 2008; Sallam *et al.*, 2017).

O PostgreSQL, um dos sistemas gerenciadores de banco de dados de código aberto mais usados, oferece desde a versão 15 um formato de log estruturado em JSON (*jsonlog*), que registra comandos, erros, conexões e falhas de autenticação com campos tipados (PostgreSQL Global Development Group, 2025a). Esse log nativo é uma fonte de dados disponível em qualquer instalação, sem extensões de auditoria nem alterações na aplicação.

Este trabalho apresenta o **SACLA** (Sistema de Análise Comportamental de Logs de Acesso), que lê o log nativo do PostgreSQL e aponta janelas de cinco minutos em que um usuário se comporta de forma atípica em relação ao próprio histórico. Para isso, usa um único algoritmo de aprendizado de máquina não supervisionado, o *Isolation Forest* (Liu; Ting; Zhou, 2008), e explica cada alerta em linguagem direta. O sistema **auxilia** a identificação de acessos anômalos: um alerta indica comportamento atípico, e a decisão sobre o que ele significa cabe a quem analisa.

## PROBLEMA DE PESQUISA

O problema que orienta o trabalho é: **é possível identificar acessos anômalos a um banco de dados PostgreSQL usando apenas o seu log nativo e aprendizado de máquina não supervisionado, com desempenho comparável ao de regras escritas por um especialista e com alertas que um analista consiga interpretar?**

Dele derivam seis questões, respondidas ao longo do texto:

1. Com que precisão e cobertura o *Isolation Forest* sinaliza acessos anômalos injetados, por tipo e intensidade?
2. O modelo detecta um tipo de anomalia que não aparece em nenhuma fase anterior ao teste?
3. O que o modelo acrescenta a um conjunto de regras simples escritas por um especialista?
4. Quanto os resultados dependem dos hiperparâmetros, do tamanho da janela e das sementes aleatórias do modelo e da simulação?
5. As conclusões se repetem em simulações novas, com hipóteses fixadas antes e teste estatístico? Quanto cada grupo de atributos contribui, e o que se perde sem o registro de linhas lidas?
6. Como cada detector se comporta quando a rotina normal dos usuários muda de forma legítima?

## OBJETIVOS

### Objetivo geral

Desenvolver e avaliar um sistema que detecte acessos anômalos a bancos de dados PostgreSQL a partir do log nativo, com aprendizado de máquina não supervisionado e alertas explicados.

### Objetivos específicos

- Configurar o registro de log do PostgreSQL para capturar comandos, erros, conexões e a quantidade de linhas lidas, e medir o custo dessa configuração.
- Construir um laboratório reprodutível, com usuários simulados, tráfego normal com ruído legítimo e anomalias injetadas com rótulos mantidos fora do log.
- Extrair do log eventos e atributos por usuário e janela de tempo, inclusive atributos relativos ao histórico de cada usuário.
- Treinar e ajustar o *Isolation Forest* com um protocolo que use o conjunto de teste uma única vez, e compará-lo a regras de especialista.
- Explicar cada alerta pelos atributos mais raros para o usuário e agrupar alertas em episódios.
- Verificar a solidez dos resultados com validação confirmatória pré-registrada, testes estatísticos, ablação de atributos e um cenário com mudanças legítimas de rotina.

## JUSTIFICATIVA

O trabalho se justifica em três frentes. Do ponto de vista prático, usa uma fonte de dados que já existe em qualquer instalação do PostgreSQL, sem depender de extensões de auditoria, de alterações nas aplicações ou de infraestrutura de análise de grande porte. Do ponto de vista técnico, o *Isolation Forest* é adequado ao problema: não exige rótulos, que raramente existem para acessos indevidos, e foi desenhado para isolar observações raras e diferentes com custo linear (Liu; Ting; Zhou, 2012). Do ponto de vista metodológico, a literatura de aprendizado de máquina aplicado à detecção de intrusão aponta que resultados promissores em laboratório muitas vezes não se sustentam fora dele, por falta de rigor na avaliação (Sommer; Paxson, 2010). Por isso, o trabalho dá peso igual ao sistema e à forma de avaliá-lo: protocolo com teste usado uma vez, comparação com uma linha de base explícita, réplicas com sementes diferentes, hipóteses registradas antes dos dados e relato dos resultados negativos.

## ESCOPO E DELIMITAÇÃO

O escopo foi fechado desde o início. O SACLA lê apenas o log nativo do PostgreSQL e usa um único algoritmo de aprendizado de máquina. Ficam de fora: a comparação entre vários algoritmos, a correlação com outros logs, extensões de auditoria como o pgAudit, o log de transações (WAL), plataformas de processamento em larga escala, bloqueio automático de acessos e interfaces acessíveis pela rede. O sistema nunca classifica um acesso como ataque. Um painel local e um monitor em lotes curtos foram construídos como ferramenta de apoio, fora da avaliação, sem alterar o modelo nem os resultados.

## ORGANIZAÇÃO DO TRABALHO

O Capítulo 2 apresenta os fundamentos: segurança de bancos de dados, o registro de log do PostgreSQL, detecção de anomalias, o *Isolation Forest*, métricas de avaliação e os métodos estatísticos usados. O Capítulo 3 discute os trabalhos relacionados. O Capítulo 4 descreve o laboratório, a simulação, o SACLA e o protocolo de avaliação. O Capítulo 5 apresenta os resultados, e o Capítulo 6 os discute, com as ameaças à validade. O Capítulo 7 conclui e indica trabalhos futuros.
