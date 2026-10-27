# FUNDAMENTAÇÃO TEÓRICA

Este capítulo reúne os conceitos em que o trabalho se apoia: a segurança de bancos de dados e o limite do controle de acesso diante de ameaças internas, o registro de log do PostgreSQL, a detecção de anomalias, o algoritmo *Isolation Forest*, as métricas usadas para avaliá-lo e os métodos estatísticos que sustentam as comparações.

## SEGURANÇA DE BANCOS DE DADOS E AMEAÇAS INTERNAS

A segurança de um banco de dados costuma ser descrita por três propriedades: confidencialidade, integridade e disponibilidade. O principal mecanismo para garantir a confidencialidade é o controle de acesso, que decide, a cada operação, se o sujeito tem permissão sobre o objeto. Bertino e Sandhu (2005) descrevem os modelos clássicos: o discricionário, em que o dono do objeto concede privilégios a outros usuários; o mandatório, baseado em níveis de classificação; e o baseado em papéis (RBAC), em que privilégios são associados a funções e os usuários recebem papéis. Os sistemas relacionais modernos, como o PostgreSQL, combinam o modelo discricionário com papéis por meio dos comandos `GRANT` e `REVOKE`.

O controle de acesso responde a uma pergunta binária: a operação é permitida ou não. Ele não avalia o contexto em que uma operação permitida acontece. Um funcionário autorizado a consultar a tabela de clientes pode consultá-la inteira, em horário incomum, a partir de uma rede externa, sem que nenhuma permissão seja violada. Esse é o terreno das ameaças internas: Cappelli, Moore e Trzeciak (2012) reúnem mais de setecentos casos de sabotagem de sistemas, roubo de propriedade intelectual e fraude cometidos por pessoas com acesso legítimo às organizações. Nesses casos, o que denuncia o problema é o uso que se faz do acesso, e não a falta de permissão. O mesmo vale para credenciais roubadas, em que o invasor herda os privilégios da vítima.

A Lei Geral de Proteção de Dados Pessoais trata a segurança como princípio, definindo-a como a "utilização de medidas técnicas e administrativas aptas a proteger os dados pessoais de acessos não autorizados e de situações acidentais ou ilícitas de destruição, perda, alteração, comunicação ou difusão" (Brasil, 2018, art. 6º, VII). A lei não prescreve as medidas concretas; detectar acessos que fogem do padrão é uma delas.

A detecção de comportamento anômalo complementa o controle de acesso. Em vez de perguntar se a operação é permitida, pergunta se ela é típica para quem a executa. Essa abordagem não depende de conhecer o ataque de antemão e pode apontar tanto um uso indevido de credencial legítima quanto um erro operacional grave.

## O REGISTRO DE LOG DO POSTGRESQL

O PostgreSQL registra eventos do servidor de acordo com parâmetros de configuração descritos na seção "Error Reporting and Logging" da documentação oficial (PostgreSQL Global Development Group, 2025a). Os que importam para este trabalho são:

- `log_destination = jsonlog`: grava cada entrada do log como um objeto JSON, com campos como horário, usuário, banco, aplicação, endereço de origem, identificador da sessão, severidade, mensagem e texto do comando. O formato, introduzido na versão 15, exige o coletor de logs (`logging_collector = on`) e é "conveniente para carregar logs em programas", segundo a documentação.
- `log_min_duration_statement = 0`: registra a duração de todos os comandos concluídos, junto com o seu texto. Com isso, cada comando gera uma linha no log.
- `log_connections` e `log_disconnections`: registram o recebimento, a autenticação e a autorização de cada conexão, e o seu encerramento. Falhas de autenticação são sempre registradas, qualquer que seja a configuração.
- `log_min_error_statement`: faz os comandos que terminam em erro aparecerem no log com o texto do comando e o código de erro (SQLSTATE), como `42501` para falta de permissão.

O log nativo não informa quantas linhas um comando retornou ou alterou. Essa informação vem do módulo `auto_explain`, que "fornece um meio de registrar automaticamente os planos de execução de comandos lentos, sem precisar executar EXPLAIN manualmente" (PostgreSQL Global Development Group, 2025b, tradução nossa). Com `auto_explain.log_min_duration = 0`, todos os planos são registrados; com `log_analyze`, o plano traz a contagem real de linhas de cada nó; com `log_format = json`, o plano vem estruturado, com o nome das tabelas acessadas. O parâmetro `log_timing = off` evita cronometrar cada nó, o que reduz o custo quando só as contagens de linhas são necessárias.

A Seção 4.2 descreve a configuração adotada e o custo medido dessa instrumentação, que é a principal limitação prática do registro de linhas.

## DETECÇÃO DE ANOMALIAS

Chandola, Banerjee e Kumar (2009) definem anomalias como padrões nos dados que não estão de acordo com uma noção bem definida de comportamento normal. Os autores distinguem três tipos: anomalias pontuais, quando uma observação isolada é atípica em relação ao conjunto; contextuais, quando a observação só é atípica em um contexto (um acesso às três da manhã é normal para uma rotina noturna e atípico para um atendente de balcão); e coletivas, quando um conjunto de observações relacionadas é atípico, embora cada uma pareça normal. Este trabalho trata as anomalias contextuais ao comparar cada janela com o histórico do próprio usuário (Seção 4.4).

Quanto à disponibilidade de rótulos, as técnicas se dividem em supervisionadas, que exigem exemplos rotulados de normalidade e de anomalia; semissupervisionadas, que aprendem só com dados normais; e não supervisionadas, que não exigem rótulos e assumem que as anomalias são raras nos dados (Chandola; Banerjee; Kumar, 2009). Em segurança de bancos de dados, rótulos de acessos indevidos são escassos e, quando existem, cobrem apenas ataques já conhecidos. Por isso, a abordagem não supervisionada é a mais natural: o modelo aprende o comportamento predominante e destaca o que foge dele, sem precisar saber de antemão como é um ataque.

Três dificuldades acompanham essa abordagem. A primeira é o desbalanceamento: anomalias são poucas, e uma taxa pequena de falsos positivos sobre milhares de janelas normais pode superar o número de verdadeiros positivos. A segunda é a deriva: o comportamento normal muda ao longo do tempo, e um modelo aprendido no passado passa a considerar atípicas rotinas novas e legítimas (Gama *et al.*, 2014). A terceira é a distância entre laboratório e produção. Sommer e Paxson (2010) argumentam que a detecção de intrusão difere das áreas em que o aprendizado de máquina costuma ter sucesso: os erros custam caro, há uma distância grande entre o alerta e a sua interpretação, o tráfego normal é muito diverso e a avaliação é difícil. Os autores recomendam avaliações que expliquem o que o modelo detecta e por quê. Essas recomendações orientaram o desenho da avaliação deste trabalho.

Goldstein e Uchida (2016) compararam 19 algoritmos de detecção de anomalias não supervisionada em 10 conjuntos de dados, considerando desempenho, custo computacional e sensibilidade a parâmetros. Comparações desse tipo estão fora do escopo deste trabalho, que fixa um único algoritmo e concentra o esforço na engenharia de atributos e no rigor da avaliação.

## ISOLATION FOREST

O *Isolation Forest* foi proposto por Liu, Ting e Zhou (2008) e detalhado na versão estendida de 2012. A ideia central é que anomalias são "poucas e diferentes" e, por isso, mais fáceis de isolar do que observações normais. Em vez de modelar a densidade ou a distância entre os pontos, o algoritmo mede quantas partições aleatórias são necessárias para separar uma observação das demais.

Uma árvore de isolamento (*iTree*) é construída sobre uma subamostra de ψ observações. Em cada nó, sorteia-se um atributo e um valor de corte entre o mínimo e o máximo desse atributo no nó; as observações são divididas em dois ramos, e o processo se repete até que cada observação fique sozinha ou a árvore atinja uma altura máxima. Uma observação atípica tende a ser isolada perto da raiz, com um caminho curto; uma observação típica, cercada de outras parecidas, exige muitas partições. A floresta reúne *t* árvores construídas sobre subamostras independentes.

O comprimento do caminho *h(x)* de uma observação *x* é o número de arestas da raiz até a folha em que ela termina. Para comparar caminhos entre subamostras de tamanhos diferentes, os autores normalizam pelo comprimento médio de uma busca malsucedida em uma árvore binária de busca com *n* elementos:

$$ c(n) = 2H(n - 1) - 2(n - 1)/n {#eq:cn}

em que *H(i)* é o número harmônico, aproximado por ln(*i*) + 0,5772156649 (constante de Euler). O escore de anomalia é:

$$ s(x, n) = 2^{-E(h(x)) / c(n)} {#eq:score}

em que *E(h(x))* é a média do comprimento do caminho de *x* nas árvores da floresta. Escores próximos de 1 indicam anomalias; escores bem abaixo de 0,5 indicam observações normais; quando todos os escores ficam perto de 0,5, os dados não têm anomalias claras (Liu; Ting; Zhou, 2008).

O algoritmo tem três propriedades úteis para este trabalho. Não usa distância nem densidade, o que dispensa normalizar atributos de escalas muito diferentes, como contagens de comandos e de linhas. Tem custo de treino proporcional a *t*·ψ·log ψ, independente do tamanho total dos dados, o que permite treinar em segundos. E funciona com subamostras pequenas: os autores mostram que subamostrar reduz os efeitos de mascaramento (anomalias numerosas que se escondem umas nas outras) e de inundação (*swamping*, normais confundidas com anomalias) (Liu; Ting; Zhou, 2012).

A implementação usada é a da biblioteca scikit-learn (Pedregosa *et al.*, 2011). Nela, o método `score_samples` devolve o oposto do escore do artigo original, em que valores menores são mais anômalos; os hiperparâmetros principais são o número de árvores (`n_estimators`, 100 por padrão), o tamanho da subamostra (`max_samples`, por padrão o menor entre 256 e o número de amostras) e a fração de atributos sorteados por árvore (`max_features`, 1,0 por padrão). O parâmetro `contamination` só define o limiar de decisão sobre os escores; ele não altera as árvores (Scikit-learn Developers, 2026). Este trabalho usa um limiar explícito, escolhido fora do modelo (Seção 4.5).

Duas limitações do algoritmo aparecem nos resultados. Como os cortes são sempre paralelos aos eixos, o escore apresenta artefatos em regiões sem dados, o que motivou extensões com cortes de inclinação aleatória (Hariri; Carrasco Kind; Brunner, 2021). E, como os cortes são sorteados entre o mínimo e o máximo observados no treino, um valor muito acima do máximo cai no mesmo ramo que um valor pouco acima dele: o escore satura fora da faixa de treino.

## MÉTRICAS DE AVALIAÇÃO

A avaliação de um detector binário parte da matriz de confusão: verdadeiros positivos (VP), falsos positivos (FP), falsos negativos (FN) e verdadeiros negativos (VN). Delas derivam:

- **precisão**, VP/(VP + FP): fração dos alertas que eram de fato anomalias;
- **recall** (ou sensibilidade), VP/(VP + FN): fração das anomalias que geraram alerta;
- **F1**, a média harmônica de precisão e recall, 2·VP/(2·VP + FP + FN);
- **taxa de falsos positivos**, FP/(FP + VN).

Quando o detector produz um escore, e não só uma decisão, é possível avaliá-lo sem fixar um limiar. A curva ROC relaciona a taxa de verdadeiros positivos e a de falsos positivos para todos os limiares, e a área sob ela (ROC-AUC) é a probabilidade de uma anomalia receber escore maior que uma observação normal sorteada. A curva precisão–recall relaciona as duas métricas, e a sua área (PR-AUC, calculada como precisão média) tem como referência a prevalência das anomalias, que é o PR-AUC de um detector aleatório. Em dados desbalanceados, a curva precisão–recall é mais informativa, porque a ROC pode parecer otimista quando os negativos são muito mais numerosos (Saito; Rehmsmeier, 2015).

Este trabalho usa também uma métrica por **cenário**: um cenário anômalo, que pode se estender por várias janelas, é considerado detectado se ao menos uma das suas janelas gera alerta. Essa métrica aproxima o que importa para quem recebe os alertas: saber que algo aconteceu, e não marcar cada janela de um mesmo episódio.

## INFERÊNCIA ESTATÍSTICA

Comparar detectores pela diferença entre médias não basta para afirmar que um é melhor que outro: é preciso estimar a incerteza e controlar a chance de encontrar diferenças por acaso. Os métodos usados neste trabalho são apresentados a seguir.

O ***bootstrap*** estima a distribuição de uma estatística reamostrando os dados com reposição. O intervalo percentil de 95% é formado pelos percentis 2,5 e 97,5 da estatística nas reamostragens (Efron; Tibshirani, 1993). Quando as observações não são independentes, como janelas consecutivas de um mesmo usuário, reamostrar observações isoladas subestima a variância; o ***bootstrap* por blocos** reamostra blocos de observações contíguas e preserva a dependência dentro de cada bloco (Künsch, 1989).

O **teste de McNemar** compara dois classificadores avaliados nos mesmos casos, usando só os casos discordantes: os que apenas o primeiro acerta e os que apenas o segundo acerta. Na forma exata, é um teste binomial sobre esses discordantes. Dietterich (1998) mostra que o teste tem baixa taxa de erro do tipo I e é adequado quando cada algoritmo pode ser executado uma única vez sobre o conjunto de teste.

O **teste de permutação pareado**, ou de aleatorização aproximada, constrói a distribuição da estatística sob a hipótese nula trocando aleatoriamente as saídas dos dois detectores dentro de cada par (Noreen, 1989). Serve para métricas como o F1, que não se decompõem em somas de casos independentes.

Quando várias hipóteses são testadas, a chance de ao menos um falso positivo cresce. A **correção de Holm** (1979) ordena os p-valores e compara o *k*-ésimo menor a α/(*m* − *k* + 1), controlando a taxa de erro da família com mais poder que a correção de Bonferroni.

Por fim, o **pré-registro** consiste em fixar e registrar as hipóteses, as análises e os critérios de decisão antes de observar os dados que vão testá-las. Ele separa a geração de hipóteses, feita com dados exploratórios, do seu teste, e evita que a pergunta mude depois de vista a resposta (Nosek *et al.*, 2018). Neste trabalho, o pré-registro foi feito com *commits* datados no repositório do projeto, antes de gerar as simulações confirmatórias (Seção 4.6).
