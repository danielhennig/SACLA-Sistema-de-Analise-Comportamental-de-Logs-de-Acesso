# METODOLOGIA

Este capítulo descreve como o trabalho foi conduzido: o laboratório em que os dados foram gerados, a simulação dos usuários e das anomalias, o funcionamento do SACLA e o protocolo usado para avaliá-lo. As decisões técnicas, com as fontes e as evidências de cada uma, estão registradas no repositório do projeto, no arquivo `docs/decisoes.md`, e são referenciadas aqui como D*n*.

## VISÃO GERAL

Não existem bases públicas rotuladas de acessos a bancos de dados com anomalias conhecidas. Para avaliar o SACLA com rótulos confiáveis, o trabalho construiu um laboratório em que todo acesso é gerado por um simulador, executado de verdade num servidor PostgreSQL e registrado pelo próprio servidor. Os rótulos das anomalias ficam num manifesto à parte, que o SACLA nunca lê. A @fig:fluxo mostra o fluxo completo.

![Fluxo do experimento: do simulador ao relatório](figuras/fluxo.png){#fig:fluxo width=15.5}

Fonte: elaborada pelo autor (2026).

O trabalho foi organizado em fases, cada uma com uma revisão ao final: ambiente e registro de log; simulação; leitura e atributos; modelo e avaliação; relatórios e documentação; monitor e painel de apoio; validação confirmatória e ablação; e tráfego não estacionário. Todo o código, a configuração e os resultados estão versionados num repositório Git.

## AMBIENTE E REGISTRO DE LOG

O servidor é o PostgreSQL 18.6, executado em Docker a partir de uma imagem fixada por *digest*. A base de dados é a Pagila, uma adaptação para PostgreSQL da base de exemplo Sakila, do MySQL, que modela uma locadora de filmes (Pagila, 2026). A versão usada foi fixada num *commit* do repositório, com o *hash* dos arquivos SQL conferido na construção da imagem, e tem 15 tabelas, entre elas 51.805 locações, 51.061 pagamentos e 999 clientes (D1, D2).

O registro de log segue o que foi descrito na Seção 2.2 (D5 a D12):

- `log_destination = jsonlog`, com o coletor de logs ligado;
- `log_min_duration_statement = 0`, para registrar todos os comandos concluídos;
- `log_connections = 'receipt,authentication,authorization'` e `log_disconnections = on`;
- `log_timezone = 'UTC'`, deixando a conversão para o horário local para a análise;
- `compute_query_id = on`, que dá a cada comando um identificador do seu formato, independente dos valores;
- `auto_explain` com `log_min_duration = 0`, `log_analyze = on`, `log_timing = off` e `log_format = json`.

Do plano de execução registrado pelo `auto_explain` saem três informações: as linhas retornadas (contagem real do nó raiz), as linhas afetadas por `INSERT`, `UPDATE` e `DELETE` (contagem do nó abaixo do `ModifyTable`) e as tabelas acessadas (todos os nomes de relação do plano). A conferência com o cliente mostrou contagens idênticas, por exemplo 51.805 linhas no plano e no cliente para uma leitura completa da tabela de locações.

O custo dessa instrumentação foi medido com uma carga fixa de 1.000 comandos, repetida cinco vezes em ordem rotativa para cada configuração, com a latência medida no cliente (@tab:custo).

Tabela: Custo do registro de log por configuração {#tab:custo}

| Configuração | Mediana (µs) | p95 (µs) | Aumento da mediana | Bytes de log por comando |
|---|---:|---:|---:|---:|
| sem registro de comandos | 790,3 | 2.235,6 | — | 0,5 |
| só comandos | 821,9 | 2.266,9 | +4,0% | 539,2 |
| comandos e auto_explain (adotada) | 865,2 | 2.995,4 | +9,5% | 10.079,0 |
| auto_explain com cronometragem dos nós | 919,9 | 3.142,5 | +16,4% | 11.348,6 |
| auto_explain em formato texto | 842,4 | 2.640,7 | +6,6% | 3.767,1 |

Fonte: elaborada pelo autor (2026).

A configuração adotada custa cerca de 10% na latência mediana e gera cerca de 10 KB de log por comando. Execuções anteriores da mesma medição variaram alguns pontos percentuais, então os valores devem ser lidos como ordem de grandeza. O formato JSON foi preferido ao texto, apesar do volume maior, porque entrega tabelas e contagens como campos tipados; no texto, as tabelas teriam de ser extraídas por expressões regulares frágeis. Esse custo é a principal limitação prática do registro de linhas, e a Seção 5.8 mede o que se perde sem ele.

Todo o processamento roda em containers com versões fixadas: Python 3.13, pandas 3.0 e scikit-learn 1.9.1, com a lista completa de dependências congelada. O mesmo comando recria o ambiente do zero em qualquer máquina com Docker.

## SIMULAÇÃO DE ACESSOS

### Usuários e comportamento normal

O laboratório tem 10 usuários em 5 papéis, cada um com privilégios mínimos concedidos por `GRANT` (D20), descritos na @tab:perfis.

Tabela: Papéis e rotinas dos usuários simulados {#tab:perfis}

| Papel | Usuários | Rotina | Origem das conexões |
|---|---:|---|---|
| atendente | 4 | turnos das 8h às 14h ou das 13h às 19h, de segunda a sábado; consultas de cadastro e registro de locações e pagamentos | rede local |
| gerente | 2 | das 9h às 18h, de segunda a sexta, com hora extra ocasional; consultas amplas, alterações de cadastro e estornos | rede local (10% externa) |
| analista | 2 | das 9h às 18h, de segunda a sexta; só leitura de dados agregados e relatórios | rede local (20% externa) |
| serviço de aplicação | 1 | 24 horas, com pico às 20h; catálogo, disponibilidade e locação pela internet | rede de aplicação |
| serviço batch | 1 | rotina diária às 2h; leituras grandes, atualização em lote e atualização de uma visão materializada | rede de aplicação |

Fonte: elaborada pelo autor (2026).

As ações de cada usuário chegam como um processo de Poisson, com uma taxa que varia de um dia para outro, e cada ação se traduz em um ou mais comandos SQL sorteados de um catálogo de consultas realistas sobre a Pagila. Cada usuário tem um gerador aleatório próprio, derivado da semente da simulação e do seu nome, de modo que mudar um usuário não altera o tráfego dos demais. A origem das conexões varia porque o container que executa a simulação está em três redes Docker (local, de aplicação e externa), e cada conexão escolhe a rede de acordo com o perfil, o que produz endereços de origem distintos no log (D14).

Para que nenhuma anomalia fosse separável por um único atributo trivial, o tráfego normal inclui ruído legítimo (D21): erros de digitação em comandos, senhas digitadas errado antes de entrar, tentativas ocasionais em tabelas sem permissão, hora extra, uma extração semanal grande feita pelos analistas e a rotina noturna volumosa do serviço batch.

### Anomalias e rótulos

Foram definidos seis tipos de anomalia, cada um em três intensidades, e um sétimo tipo, **inédito**, que só aparece no teste (D22), conforme a @tab:anomalias.

Tabela: Tipos de anomalia injetados e as suas intensidades {#tab:anomalias}

| Tipo | Descrição | Baixa / média / alta |
|---|---|---|
| rajada | taxa de comandos muito acima da normal do usuário, por 3 a 8 minutos | 3× / 8× / 20× |
| fora do horário | sessão em horário em que o usuário nunca trabalha | 5 / 20 / 60 comandos |
| volume alto | leitura de muitas linhas | 2 mil / 10 mil linhas / tabelas inteiras |
| sem permissão | tentativas em tabelas sem `GRANT` | 1 a 2 / 5 / 15 tentativas |
| falha de autenticação | tentativas de login com senha errada | 3 / 10 / 40 tentativas |
| DML incomum | `UPDATE` ou `DELETE` permitido, mas em volume atípico | 5 / 50 / 500 linhas |
| leitura atípica (inédito) | paginação lenta de tabelas permitidas, em horário e ritmo normais | 8 / 20 / 40 páginas |

Fonte: elaborada pelo autor (2026).

O tipo inédito não foi usado para escrever as regras da linha de base nem para ajustar o modelo. Ele representa um acesso que não fere nenhuma permissão e não tem volume extremo em nenhum comando isolado: um usuário que lê, página por página, dados que normalmente não consulta.

Em 28 dias simulados, são 20 cenários no período de treino, com tipo e intensidade sorteados, simulando a contaminação que um histórico real teria; 5 cenários por tipo e intensidade na validação (90 no total); e 8 por tipo e intensidade no teste (144), mais 12 do tipo inédito, um por combinação de papel e intensidade.

Cada cenário é registrado num manifesto com usuário, tipo, intensidade e intervalo de tempo. Os eventos que o executor envia ao banco e o log gerado não carregam nenhum rótulo (D23). O SACLA nunca lê o manifesto; só a avaliação o lê.

### Geração dos logs com horários simulados

Quatro semanas de atividade não podem ser executadas em tempo real. A solução adotada tem três passos (D13): a agenda é gerada em tempo simulado; os eventos são executados em sequência, o mais rápido possível, em cerca de 100 segundos; e cada linha do log recebe depois o horário simulado do seu evento. A ligação entre linha e evento usa um comentário opaco acrescentado a cada comando, removido no remapeamento. O log remapeado tem exatamente o formato do jsonlog original, e o SACLA o lê como leria um log real.

Verificações automáticas acompanham cada simulação: nenhuma linha de cliente pode ficar sem evento, a ordem cronológica tem de ser preservada e o manifesto tem de ser coerente com o log remapeado. Na simulação de referência, as 207.769 linhas de cliente foram remapeadas, e as contagens de linhas dos planos coincidiram com as recebidas pelo cliente em 94.174 comparações.

## O SACLA

O SACLA tem quatro módulos, todos independentes do simulador e da avaliação: o pacote do sistema não importa nenhum dos dois, e um teste automatizado garante essa separação.

### Leitura e eventos

O primeiro módulo lê os arquivos do jsonlog, inclusive comprimidos, na ordem de rotação. Linhas malformadas ou truncadas são contadas e ignoradas (D26). O segundo transforma as linhas em cinco tipos de evento: comando concluído, comando com erro, falha de autenticação, conexão e desconexão (D27). Cada plano do `auto_explain` é associado ao comando correspondente pela sessão e pelo texto do comando. Cada comando é classificado como `SELECT`, `INSERT`, `UPDATE`, `DELETE`, DDL ou outro (D28). Ao montar o conjunto de dados, os eventos extraídos são conferidos, usuário por usuário, com o que o executor fez; a conferência passou em todas as simulações (D31).

### Janelas e atributos

Os eventos são agregados por usuário em janelas fixas de cinco minutos, alinhadas ao relógio. Só existem janelas em que o usuário teve alguma atividade. Cada janela recebe 28 atributos (D29), agrupados na @tab:atributos.

Tabela: Atributos calculados para cada usuário e janela de cinco minutos {#tab:atributos}

| Grupo | Atributos |
|---|---|
| Volume de comandos | total; por tipo (`SELECT`, `INSERT`, `UPDATE`, `DELETE`, DDL, outros) |
| Erros e acesso | comandos com erro; erros de permissão; falhas de autenticação; conexões |
| Dados | linhas retornadas (soma e máximo); linhas afetadas |
| Desempenho | duração média, máxima e percentil 95 dos comandos |
| Diversidade | tabelas distintas; endereços IP distintos |
| Tempo | hora do dia (seno e cosseno); fim de semana |
| Relativos ao histórico do usuário | z robusto de comandos e de linhas retornadas; raridade da hora; frações de tabelas, IPs e formatos de consulta nunca vistos |

Fonte: elaborada pelo autor (2026).

Os seis atributos relativos comparam a janela com o histórico do próprio usuário e são a forma de tratar as anomalias contextuais (Seção 2.3):

- o **z robusto** de comandos é a diferença entre o número de comandos da janela e a mediana do usuário, dividida por 1,4826 vezes o desvio absoluto mediano (MAD), com piso 1; o de linhas usa o logaritmo de 1 mais as linhas retornadas;
- a **raridade da hora** é o logaritmo negativo da frequência daquela hora no histórico do usuário, com suavização de Laplace;
- as **frações de novidade** são as frações de tabelas, de endereços IP e de formatos de consulta (pelo identificador `query_id`) da janela que nunca apareceram no histórico do usuário.

O histórico usa apenas janelas do período de treino. Nenhuma informação da validação ou do teste entra nesse cálculo, o que é verificado por testes automatizados. Um usuário sem histórico recebe uma referência neutra.

Há um cuidado adicional com as janelas do próprio treino. Se cada janela de treino fosse comparada com o histórico inteiro, que inclui a própria janela, nada no treino seria "novo": as frações de novidade valeriam sempre zero, e o *Isolation Forest*, que só corta atributos que variam na amostra, as ignoraria. Esse defeito existiu na primeira versão da avaliação (D41) e foi corrigido comparando cada janela de treino com o histórico do usuário **sem o seu dia**, o que este trabalho chama de "deixando um dia de fora" (D45). Assim, treino e teste passam a ter atributos relativos da mesma natureza. A Seção 5.6 compara as duas versões.

### Modelo, limiar e explicação

O modelo é o *Isolation Forest* da biblioteca scikit-learn, treinado com todas as janelas do período de treino, sem rótulos. As contagens recebem a transformação log(1 + *x*), que reduz a assimetria das distribuições. O escore de anomalia é o oposto de `score_samples`, de modo que valores maiores indicam janelas mais atípicas, e uma janela gera alerta quando o escore passa de um limiar explícito (D32).

Na avaliação, o limiar é o de melhor F1 na validação (Seção 4.5). No uso real, em que não há rótulos, o limiar é o escore acima do qual fica uma fração fixa das janelas do próprio histórico: o analista diz quantos alertas aceita receber num período normal (D40). Na configuração avaliada, essa fração é de 2,13%.

Cada alerta é explicado pelos atributos mais raros para aquele usuário (D42). Para cada atributo, mede-se a fração das janelas do histórico do usuário com valor maior ou igual ao da janela; entram na explicação até três atributos com essa fração abaixo de 5%, do mais raro ao menos raro. O texto é escrito para quem analisa, por exemplo: "linhas retornadas (soma): 112.507 (acima do máximo do histórico; mediana 61, máximo 10.072)" ou "horário incomum para o usuário: 03h (0,0% das janelas do histórico)". Essa explicação é descritiva, do que mais foge do normal do usuário, e não a atribuição interna do modelo; quando nenhum atributo isolado é raro, o alerta informa que a combinação de valores é que é incomum.

Alertas seguidos do mesmo usuário, separados por no máximo uma janela, formam um **episódio**, que é a unidade examinada pelo analista (D43). O relatório, em HTML e CSV, lista os episódios do mais atípico ao menos atípico, com a explicação e um resumo de cada janela. Os comandos `sacla fit` e `sacla score` aplicam o mesmo fluxo a qualquer jsonlog, sem rótulos e sem o laboratório (D39).

## PROTOCOLO DE AVALIAÇÃO

### Rótulos e divisão temporal

Uma janela de cinco minutos de um usuário é rotulada como anômala se algum cenário do manifesto do mesmo usuário intercepta o seu intervalo (D30). O rótulo serve só para avaliar. Os 28 dias são divididos em ordem temporal: as semanas 1 e 2 para treino, a semana 3 para validação e a semana 4 para teste (@tab:divisao).

Tabela: Janelas por período na simulação de referência {#tab:divisao}

| Período | Janelas | Anômalas | Contaminação |
|---|---:|---:|---:|
| Treino | 9.109 | 34 | 0,37% |
| Validação | 4.684 | 176 | 3,76% |
| Teste | 4.662 | 337 | 7,23% |

Fonte: elaborada pelo autor (2026).

O treino contém anomalias, como aconteceria num histórico real, e o modelo é treinado com todas as janelas, sem saber quais são.

### Ajuste e teste

Os hiperparâmetros foram escolhidos **só na validação** (D33), numa grade de 54 combinações: número de árvores em {100, 200, 500}, tamanho da subamostra em {256, 1.024, 10% do treino}, fração de atributos por árvore em {0,5; 0,75; 1,0} e uso ou não da transformação logarítmica. Cada combinação foi treinada com cinco sementes; para cada uma, o limiar de melhor F1 na validação. A escolhida foi a de maior F1 médio, com desempate pela PR-AUC: 200 árvores, 1.024 amostras por árvore, 50% dos atributos e transformação logarítmica, com F1 de 61,0% na validação.

No teste, a configuração escolhida foi treinada com dez sementes do modelo, e o limiar de cada semente veio da validação. Os resultados são a média das dez sementes, com o desvio-padrão.

### Linhas de base

O *Isolation Forest* ajustado foi comparado com três alternativas:

- **IF sem rótulos:** os parâmetros padrão do scikit-learn e o limiar no quantil de 99% dos escores do próprio treino, o que se obteria sem nenhuma janela rotulada;
- **regras de especialista:** seis regras com limiares fixados antes da avaliação, com as estatísticas por usuário calculadas só no treino (D34): três ou mais falhas de autenticação; um ou mais erros de permissão; comandos acima de três vezes o percentil 99 do usuário; linhas retornadas acima do máximo do usuário; linhas afetadas acima do máximo do usuário; e hora nunca vista para o usuário;
- **IF ∪ regras:** uma janela gera alerta se o *Isolation Forest* ou qualquer regra a sinaliza.

As regras foram escritas conhecendo os seis tipos de anomalia, o que as favorece; o tipo inédito não tem regra própria.

### Métricas e análises complementares

As métricas são as da Seção 2.5: precisão, recall, F1, falsos positivos, ROC-AUC e PR-AUC por janela; recall por tipo e intensidade; e a fração de cenários detectados, em que um cenário é detectado se ao menos uma de suas janelas gera alerta. Também se mediu o tempo de cada etapa.

Duas análises complementares não tocam o teste. A **sensibilidade** varia um hiperparâmetro de cada vez e o tamanho da janela (1, 5 e 15 minutos), sempre na validação (D35). A **robustez** reavalia a configuração congelada em duas simulações novas, com sementes 7 e 2026, escolhendo em cada uma só o limiar, na validação dela (D36).

O conjunto de teste da simulação de referência foi usado uma vez na primeira versão da avaliação (v1) e uma segunda vez na versão corrigida (v2), depois da correção dos atributos relativos descrita na Seção 4.4. A correção foi motivada por uma análise sem rótulos, que mostrou atributos constantes no treino, e não pelo desempenho, e o protocolo da v2 é idêntico ao da v1. As duas versões são reportadas. A validação confirmatória, descrita a seguir, responde a esse uso duplo.

## VALIDAÇÃO CONFIRMATÓRIA PRÉ-REGISTRADA

Para confirmar os resultados em dados nunca vistos e testar as diferenças entre detectores, foi feito um **pré-registro** (D52). Antes de gerar qualquer dado novo, um *commit* no repositório fixou:

- a configuração congelada do modelo (a da v2), as regras e o protocolo da robustez;
- cinco sementes de simulação nunca usadas: 101, 202, 303, 404 e 505, com 780 cenários de teste no total, 60 do tipo inédito;
- três hipóteses, os testes e o nível de significância (@tab:hipoteses-confirmatorias);
- o compromisso de relatar os resultados como saíssem.

Tabela: Hipóteses da validação confirmatória {#tab:hipoteses-confirmatorias}

| | Pergunta | Medida | Teste |
|---|---|---|---|
| H1 | O IF acrescenta cenários às regras? | cenários detectados, IF ∪ regras × regras | McNemar exato |
| H2 | A combinação muda o F1 por janela em relação às regras? | F1, IF ∪ regras × regras | permutação pareada por blocos |
| H3 | O IF detecta o tipo inédito melhor que as regras? | cenários inéditos detectados, IF × regras | McNemar exato |

Fonte: elaborada pelo autor (2026).

Os testes são bicaudais, com α = 0,05 e correção de Holm sobre as três hipóteses, no agregado das cinco semanas de teste. Um cenário conta como detectado pelo *Isolation Forest* quando é detectado em ao menos metade das dez sementes do modelo. Na permutação, o bloco é o par usuário e dia local, porque janelas vizinhas não são independentes; a estatística é a diferença de F1, com 10.000 permutações. Os intervalos de confiança de 95% são obtidos por *bootstrap* percentil com 2.000 reamostragens, estratificado por simulação: blocos usuário e dia para as métricas por janela, cenários para a fração de cenários detectados. As expectativas foram registradas junto com as hipóteses: H1 e H3 a favor do *Isolation Forest* e H2 sem diferença.

## ABLAÇÃO DE ATRIBUTOS

Para medir a contribuição de cada grupo de atributos, cada grupo foi retirado do modelo, um de cada vez, com os hiperparâmetros congelados (D52, D54). A análise é exploratória e usa apenas o treino e a validação das oito simulações disponíveis (as sementes 42, 7, 2026 e as cinco confirmatórias), com as cinco sementes de ajuste; o teste nunca é usado, e o código recusa qualquer janela de teste. Os grupos retirados são: os atributos relativos ao histórico; os de novidade; os de horário; os de origem; e os que dependem do `auto_explain` (linhas e tabelas). Neste último caso, as regras também perdem as duas regras de linhas, e a combinação usa as duas versões reduzidas. Mede-se a variação do F1 (no melhor limiar da validação), da PR-AUC e da fração de cenários detectados em relação ao conjunto completo, com intervalo *t* de 95% entre as oito simulações.

## TRÁFEGO NÃO ESTACIONÁRIO

A última análise trata a principal ameaça à validade dos dados sintéticos: usuários regulares demais. Um catálogo de sete mudanças legítimas de rotina foi fixado antes de qualquer simulação com essas mudanças, num segundo pré-registro (D55), descrito na @tab:mudancas.

Tabela: Mudanças legítimas de rotina e o detector que cada uma deve afetar {#tab:mudancas}

| Mudança | Quem e quanto | Afeta no IF | Afeta nas regras |
|---|---|---|---|
| troca de turno | 2 atendentes, permanente | hora, raridade da hora | hora nunca vista |
| férias | 2 entre atendentes, gerentes e analistas, de 7 a 9 dias | histórico menor | — |
| pico de movimento | 2 entre atendentes e serviço web, de 3 a 7 dias, 1,5× a 2,5× a taxa | comandos | comandos acima do p99 |
| crescimento | serviço web, permanente, +10% por semana | comandos | comandos acima do p99 |
| home office | 2 entre gerentes e analistas, permanente, 50% externa | IPs, IP inédito | — |
| nova rotina | 1 analista, relatório semanal em tabelas nunca usadas | tabelas e formatos inéditos | talvez linhas acima do máximo |
| plantão | 1 gerente, um sábado | fim de semana, hora | hora nunca vista |

Fonte: elaborada pelo autor (2026).

A coluna "afeta" foi escrita antes dos dados para mostrar que o catálogo inclui mudanças desfavoráveis aos dois lados, inclusive algumas que só o *Isolation Forest* enxerga. O início de cada mudança é sorteado entre os dias 8 e 27, e as janelas afetadas continuam **normais**: as mudanças são legítimas. O plano sorteado fica num arquivo à parte, usado só para analisar os alarmes falsos. Sem as mudanças, a simulação é idêntica à anterior, o que foi conferido pelo *hash* da agenda gerada.

Dez sementes foram simuladas sem e com as mudanças: as cinco confirmatórias e cinco novas (606, 707, 808, 909 e 1010). Foram pré-registradas duas hipóteses, com Holm sobre as duas:

- **H4:** a perda de F1 com as mudanças difere entre o *Isolation Forest* e as regras. A medida é a diferença das diferenças por semente, [F1 do IF com − sem] − [F1 das regras com − sem], com teste *t* pareado nas dez sementes; aqui a simulação é a unidade, e a variação entre simulações entra no teste. A expectativa registrada foi de que o *Isolation Forest* perderia menos.
- **H5:** com as mudanças, a combinação IF ∪ regras ainda detecta mais cenários que as regras (McNemar exato, como H1).

## REPRODUTIBILIDADE E VERIFICAÇÃO

Toda a avaliação é reproduzível por comandos de um único script de tarefas, com as sementes fixadas: simulações 42, 7 e 2026 e as confirmatórias e de deriva citadas acima; sementes de ajuste de 0 a 4 e de avaliação de 0 a 9. Refazer a avaliação produz exatamente as mesmas métricas; a cada fase, os números das fases anteriores foram reproduzidos com diferença máxima da ordem de 10⁻¹⁶. O código tem 206 testes automatizados, verificação de tipos e formatação automática, e cada simulação passa pelas verificações descritas na Seção 4.3.
