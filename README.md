# JIRA SLA Medallion Pipeline (v4)

Projeto Python de Engenharia de Dados com arquitetura **Medallion (Bronze / Silver / Gold)** para ingestao de issues do JIRA (JSON), normalizacao e calculo de SLA em **horas uteis** (excluindo fins de semana e feriados nacionais do Brasil).

O pipeline suporta:
- Ingestao do **Azure Blob Storage** via **Service Principal** (somente leitura)
- **Fallback local** (offline) para `data/raw/jira_issues_raw.json`
- Ambiente corporativo com proxy TLS (certificado self-signed) via **CA bundle** (`AZURE_CA_BUNDLE`)
- Execucao **por etapas (step)** com validacoes fail-fast (padrao)
- Execucao **full** (opcional)

---

## Arquitetura (Medallion)

### Bronze
- Objetivo: copia fiel do dado de origem (sem transformacao)
- Entrada: Azure Blob JSON (ou fallback local)
- Saidas:
  - `data/bronze/bronze_jira.json`
  - `data/bronze/bronze_jira_source.json` (evidencia: AZURE_BLOB ou LOCAL_FALLBACK)

### Silver
- Objetivo: normalizar JSON aninhado em tabela CSV enxuta focada no SLA
- Entrada: `data/bronze/bronze_jira.json`
- Saida:
  - `data/silver/silver_jira.csv`

Colunas Silver:
- `issue_id`, `issue_key`, `created`, `resolved`, `status`, `priority`, `issue_type`, `assignee`

### Gold
- Objetivo: aplicar regra de negocio e calcular SLA em horas uteis
- Entrada: `data/silver/silver_jira.csv`
- Saidas:
  - `data/gold/gold_jira_sla.csv`
  - `data/gold/gold_sla_by_analyst.csv`
  - `data/gold/gold_sla_by_type.csv`
  - `data/gold/gold_sla_by_issue_type.csv` (mesmo conteudo, nome alternativo)

Regras Gold:
- Considera apenas `status` em `Done` ou `Resolved`
- `resolved` deve estar preenchido
- SLA esperado por prioridade:
  - High = 24
  - Medium = 72
  - Low = 120
- Calcula `actual_hours` em **horas uteis**:
  - exclui sabado/domingo
  - exclui feriados nacionais do Brasil

Colunas Gold:
- `issue_id`, `issue_key`, `created`, `resolved`, `status`, `priority`,
  `issue_type`, `assignee`, `actual_hours`, `sla_expected_hours`, `is_sla_met`

---

## Requisitos

- Windows 10/11
- Python 3.9+
- PowerShell
- Conta Azure + Storage Blob com permissao de leitura para o Service Principal

---

## Setup (Passo a passo)

### 1) Criar ambiente virtual
Na raiz do projeto:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip