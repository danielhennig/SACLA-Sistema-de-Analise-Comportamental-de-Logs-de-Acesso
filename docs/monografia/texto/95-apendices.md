# APÊNDICE A – CONFIGURAÇÃO DE LOG DO POSTGRESQL {-}

Configuração incluída no servidor do laboratório (arquivo `docker/postgres/sacla.conf` do repositório). A justificativa de cada parâmetro, com a documentação oficial, está em `docs/decisoes.md` (D5 a D12).

```
# Destino e arquivos
logging_collector = on                  # obrigatório para jsonlog
log_destination = 'jsonlog'
log_directory = '/var/log/postgresql/sacla'
log_filename = 'postgresql-%Y%m%d_%H%M%S.log'
log_file_mode = 0644
log_rotation_age = 0
log_rotation_size = 100MB
log_timezone = 'UTC'

# Conexões (falhas de autenticação são registradas sempre)
log_connections = 'receipt,authentication,authorization'
log_disconnections = on

# Comandos: uma linha por comando concluído, com duração e texto
log_statement = 'none'
log_min_duration_statement = 0
log_min_error_statement = error
compute_query_id = on

# Linhas retornadas e afetadas (auto_explain)
shared_preload_libraries = 'auto_explain'
auto_explain.log_min_duration = 0
auto_explain.log_analyze = on
auto_explain.log_timing = off
auto_explain.log_buffers = off
auto_explain.log_format = 'json'
auto_explain.log_nested_statements = off
auto_explain.sample_rate = 1
auto_explain.log_level = 'LOG'
```

# APÊNDICE B – REPRODUÇÃO DO EXPERIMENTO {-}

O código, a configuração e os resultados estão no repositório do projeto. Com o Docker em execução, os comandos abaixo recriam o ambiente e reproduzem cada análise; todo o processamento roda em containers com versões fixadas.

```
python tasks.py setup        # imagens, banco e Pagila do zero
python tasks.py smoke        # gera eventos conhecidos e confere o jsonlog
python tasks.py bench        # mede o custo do registro de log
python tasks.py simulate     # 28 dias simulados, semente 42
python tasks.py features     # janelas de 5 minutos, atributos e rótulos
python tasks.py evaluate     # ajuste na validação, teste, regras e sensibilidade
python tasks.py robustness --exp-id sim-s42-28d__w5m__ne200-ms1024-mf0.5-log1
python tasks.py report       # relatório de anomalias e figuras
python tasks.py confirm  --exp-id sim-s42-28d__w5m__ne200-ms1024-mf0.5-log1
python tasks.py ablation --exp-id sim-s42-28d__w5m__ne200-ms1024-mf0.5-log1
python tasks.py drift    --exp-id sim-s42-28d__w5m__ne200-ms1024-mf0.5-log1
python tasks.py test         # testes automatizados
```

Para usar o SACLA em um log real, sem rótulos:

```
python tasks.py fit   --logs /logs --until 2026-03-16T03:00:00Z --model data/sacla/detector.joblib
python tasks.py score --logs /logs --since 2026-03-23T03:00:00Z --model data/sacla/detector.joblib --out data/sacla/relatorio
```

O comando `fit` aprende com um período considerado normal, e o `score` analisa outro período e gera o relatório em HTML e CSV.
