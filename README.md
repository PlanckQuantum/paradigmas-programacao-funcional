# Versão funcional do projeto de tarifas da ANEEL

Esta pasta contém versões adaptadas dos cinco arquivos Python enviados.

## Critérios adotados

- **`map`**: transformação de registros e preparação de estruturas de saída.
- **`filter`**: seleção de tarifas vigentes, perfis comparáveis e entradas válidas.
- **`reduce`**: soma/contagem de tarifas e consolidação de distribuidoras sem mutação do acumulador.
- **`lambda`**: predicados, transformações, chaves de ordenação e funções simples.
- **Sem `for` nem `while` explícitos e sem compreensões** nos cinco módulos adaptados.
- **`dataclass(frozen=True)`** para representar valores imutáveis.
- As funções `def` restantes atendem sobretudo a validação, tratamento de erros e entrada/saída. Em Python, `lambda` não oferece `raise`, `try/except` nem `with` como instruções.
- A paginação de `baixar_dados.py` foi convertida para recursão em vez de `while`.

## Arquivos

- `processamento.py`: filtra e normaliza registros da ANEEL.
- `analise.py`: calcula médias, classificações e diferenças de tarifas por UF.
- `arquivos.py`: lê/grava CSV e JSON (bordas com efeitos colaterais).
- `baixar_dados.py`: consulta a ANEEL e a malha do IBGE (precisa de internet).
- `exportar_frontend.py`: constrói `interface/src/data/painel.json`.

## Como integrar ao projeto

1. Faça backup dos cinco `.py` originais.
2. Copie os cinco arquivos desta pasta para **a pasta raiz do projeto**, substituindo os homônimos.
3. Mantenha os diretórios `dados/` e `interface/` da versão original.
4. Execute `python exportar_frontend.py` para reconstruir o JSON, se os arquivos em `dados/` já estiverem presentes.
5. Para refazer a coleta, execute `python baixar_dados.py --anos 2024 2025` (requer internet e a existência das referências correspondentes na fonte).

## Validação realizada

Os cinco arquivos passaram na compilação de sintaxe do Python. Também foi feita uma comparação com os scripts originais, em um cenário sintético que verifica seleção de perfis, tarifas inválidas, duplicatas, conflitos, mapeamentos por UF, médias, ranking, CSV, geração de JSON e paginação com respostas simuladas. A saída foi idêntica nesse cenário.

**Limite:** não houve teste real de conexão com as APIs ANEEL/IBGE nem execução com os arquivos completos em `dados/`, que não foram fornecidos.
