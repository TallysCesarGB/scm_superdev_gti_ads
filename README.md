# 🛒 SCM Suite — Sistema de Gestão da Cadeia de Suprimentos

> Projeto acadêmico desenvolvido para a disciplina **Aplicações Corporativas**  
> Curso Superior em Análise e Desenvolvimento de Sistemas — IFRN Campus Pau dos Ferros  
> Prof. Sergio Neto

---

## 📋 Sobre o Projeto

O **SCM Suite** é um sistema web fullstack construído em **Django** que simula uma plataforma de gestão da cadeia de suprimentos (Supply Chain Management) para um supermercado de grande porte. O sistema integra análise de dados históricos de vendas, inteligência artificial para recomendação de compras e simulação de troca eletrônica de dados (EDI) entre o supermercado e seus fornecedores.

### Conceitos de SCM Aplicados

| Conceito | Implementação no sistema |
|---|---|
| **Curva ABC** | Dashboard calcula automaticamente quais 20% dos produtos geram 80% do faturamento |
| **Efeito Chicote** | IA analisa variações de demanda e evita superpedidos por picos pontuais |
| **Estoque de Segurança** | Recomendações incluem 10% adicional sobre a demanda projetada |
| **EDI B2B** | Geração de mensagens no padrão ANSI ASC X12 850 (Purchase Order) |
| **Sazonalidade** | Gráfico de padrão de vendas por dia da semana e tendência semanal |
| **Ponto de Pedido** | IA considera prazo de entrega do fornecedor no cálculo da quantidade |

---

## 🚀 Como Instalar e Rodar

### Pré-requisitos

- Python 3.10 ou superior
- pip

### Passo a passo

```bash
# 1. Clone o projeto
SSH: git@github.com:TallysCesarGB/scm_superdev_gti_ads.git
HTTPS: https://github.com/TallysCesarGB/scm_superdev_gti_ads.git

# 2. Criar e ativar ambiente virtual
python3 -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate         # Windows

# 3. Instalar dependências
pip install django pandas openpyxl plotly

# 4. Garantir que a planilha está no lugar certo
# O arquivo deve estar em: scm_project/scm/dados_vendas_supermercado_v2.xlsx

# 5. Rodar as migrações
python manage.py migrate

# 6. Popular o banco de dados com os dados da planilha
python manage.py seed_data

# 7. Iniciar o servidor
python manage.py runserver
```

Acesse **http://localhost:8000** no navegador.

---

## 🗂️ Estrutura do Projeto

```
scm_project/
├── manage.py
├── scm_project/
│   ├── settings.py          # Configurações Django
│   └── urls.py              # Rotas principais
├── scm/
│   ├── models.py            # Modelos de dados
│   ├── views.py             # Lógica das páginas e APIs
│   ├── dados_vendas_supermercado_v2.xlsx
│   └── management/
│       └── commands/
│           └── seed_data.py # Importação da planilha + dados fictícios
├── templates/
│   └── scm/
│       ├── base.html        # Layout base com sidebar
│       ├── dashboard.html   # Painel executivo
│       ├── produtos.html    # Catálogo de produtos
│       ├── fornecedores.html
│       ├── pedidos_edi.html
│       ├── detalhe_pedido.html
│       └── ia_recomendacao.html
└── static/
```

---

## 📄 Páginas do Sistema

### 1. Dashboard Executivo `/`

Visão geral para a diretoria com:

- **4 KPIs** no topo: Faturamento 30 dias, Produtos Ativos, Pedidos EDI em aberto, Fornecedores
- **Gráfico de linha** — Faturamento semanal dos últimos 90 dias
- **Gráfico de rosca** — Faturamento por categoria (Mercearia, Bebidas, Perecíveis etc.)
- **Gráfico de barras** — Padrão de vendas por dia da semana (fins de semana destacados)
- **Tabela Curva ABC** — Top 15 produtos por faturamento, classificados em A/B/C automaticamente
- **Alertas de estoque crítico** — Produtos abaixo do estoque mínimo

### 2. Produtos `/produtos/`

- Listagem completa dos 25 SKUs com filtro por categoria
- Barra de progresso visual do estoque atual vs mínimo
- Indicador de alerta para produtos críticos
- Vendas dos últimos 7 dias por produto
- Tag visual para produtos perecíveis

### 3. Fornecedores `/fornecedores/`

- 5 fornecedores fictícios do Nordeste com CNPJ, contato, e-mail e telefone
- Prazo de entrega em dias
- Barra de avaliação (0–5)
- Total de pedidos e volume financeiro por fornecedor

### 4. Pedidos EDI `/pedidos/`

- Pipeline de status: Gerado → Enviado → Confirmado → Em Trânsito → Entregue
- KPIs de pedidos por status e valor total
- Clique em qualquer pedido para ver a mensagem EDI completa

### 5. Detalhe do Pedido `/pedidos/<id>/`

- Informações completas do pedido
- Lista de itens com quantidade sugerida pela IA vs quantidade pedida
- Justificativa gerada pela IA
- Mensagem EDI no formato **ANSI ASC X12 850** com todos os segmentos

### 6. IA Recomendação `/ia/`

- Selecione qualquer produto
- Informe contexto opcional (feriados, promoções da concorrência, previsão de tempo etc.)
- A IA analisa os últimos 30 dias e retorna:
  - Quantidade recomendada para a próxima semana
  - Justificativa detalhada
  - Nível de risco (Baixo / Médio / Alto)
  - Ação sugerida ao comprador
- Botão para gerar o pedido EDI diretamente a partir da recomendação
- Histórico de todas as recomendações geradas

---

## 🤖 Integração com IA

O sistema utiliza a **API da Anthropic (Claude)** — modelo `claude-sonnet-4-6`.

### Como funciona

1. O comprador seleciona um produto e informa o contexto
2. O sistema busca os dados de vendas dos **últimos 30 dias** no banco
3. Monta um prompt estruturado com: média diária, projeção 7 dias, estoque atual, prazo do fornecedor e contexto
4. Envia para a API do Claude e exibe a resposta formatada
5. **Fallback automático**: se a API estiver indisponível, o sistema calcula localmente com a fórmula `(média_diária × 7 × 1,1) - estoque_atual + estoque_mínimo`

### Exemplo de prompt enviado

```
Você é um especialista em SCM de supermercados de grande porte no Brasil.

Produto: Leite Integral 1L (SKU: PERE001)
Categoria: Perecíveis | Perecível: Sim
Estoque atual: 746 unidades | Estoque mínimo: 20 unidades
Fornecedor: FrigoNorte Carnes e Derivados (prazo: 1 dia)

Período analisado: 2025-12-01 a 2025-12-31 (30 dias)
Total vendido: 2.550 unidades | Média diária: 85 unidades/dia
Projeção 7 dias: 595 unidades

Contexto: Feriado de Ano Novo na próxima semana
```

---

## 📡 EDI Simulado

O sistema gera mensagens no padrão **ANSI ASC X12 — Transação 850 (Purchase Order)**.

### Segmentos gerados

| Segmento | Descrição |
|---|---|
| `ISA` | Envelope de intercâmbio (identificação do remetente/destinatário) |
| `GS` | Cabeçalho do grupo funcional |
| `ST*850` | Início da transação Purchase Order |
| `BEG` | Início do pedido (número, data) |
| `REF` | Referência ao sistema SCM-AI |
| `DTM` | Data prevista de entrega |
| `N1/N3/N4` | Endereço de entrega |
| `PO1` | Linha do pedido (SKU, quantidade, preço) |
| `CTT` | Total de linhas |
| `AMT` | Valor total da transação |
| `SE/GE/IEA` | Encerramentos de transação, grupo e intercâmbio |

---

## 🗃️ Banco de Dados

### Modelos

- **Categoria** — 7 categorias (Mercearia, Bebidas, Perecíveis, Limpeza, Higiene, Carnes, Hortifruti)
- **Fornecedor** — 5 distribuidoras fictícias do Nordeste
- **Produto** — 25 SKUs com estoque, preço e fornecedor vinculado
- **VendaHistorica** — 9.125 registros importados da planilha (Jan–Dez 2025)
- **PedidoEDI** — Pedidos com status, mensagem EDI e justificativa da IA
- **ItemPedido** — Itens de cada pedido com quantidade sugerida vs pedida
- **RecomendacaoIA** — Histórico de todas as consultas feitas à IA

### Data de referência

O sistema usa `DATA_BASE = 2025-12-31` como data fixa de referência.  
Todos os filtros ("últimos 30 dias", "últimos 90 dias") são calculados a partir dessa data, garantindo que os dados da planilha sempre apareçam nos relatórios independentemente da data atual do computador.

---

## 🏭 Fornecedores Fictícios

| Fornecedor | Categorias | Prazo | Avaliação |
|---|---|---|---|
| Distribuidora NordestePrime Ltda | Limpeza, Mercearia | 2 dias | ⭐ 4.8 |
| Atacadão São Francisco S/A | Higiene | 3 dias | ⭐ 4.5 |
| FrigoNorte Carnes e Derivados | Perecíveis, Carnes | 1 dia | ⭐ 4.6 |
| BevMax Bebidas do Nordeste | Bebidas | 2 dias | ⭐ 4.3 |
| HortiFresh Distribuição | Hortifruti | 1 dia | ⭐ 4.7 |

---

## 🔧 Tecnologias Utilizadas

| Tecnologia | Uso |
|---|---|
| **Django 6** | Framework web backend |
| **SQLite** | Banco de dados (padrão Django) |
| **openpyxl** | Leitura da planilha Excel |
| **Chart.js 4** | Gráficos interativos no dashboard |
| **Anthropic Claude API** | Motor de IA para recomendações |
| **ANSI ASC X12** | Padrão EDI para pedidos de compra |
| HTML/CSS puro | Frontend sem frameworks externos |

---

## 📚 Referências

- PRADO, E. P. V.; SOUZA, C. A. **Fundamentos de sistemas de informação**. Elsevier, 2014.
- LAUDON, K. C.; LAUDON, J. P. **Sistemas de informações gerenciais**. 11ª ed. Pearson, 2014.
- Documentação oficial Django — https://docs.djangoproject.com
- Anthropic API Docs — https://docs.anthropic.com
- Padrão EDI X12 850 — https://www.stedi.com/edi/x12/transaction-set/850