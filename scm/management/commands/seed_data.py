import random
import datetime
from pathlib import Path
from django.core.management.base import BaseCommand
from django.utils import timezone
import openpyxl
from scm.models import Categoria, Fornecedor, Produto, VendaHistorica, PedidoEDI, ItemPedido

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # → scm/
XLSX_PATH = BASE_DIR / 'dados_vendas_supermercado_v2.xlsx'

# Data de referência do sistema — última data da planilha
DATA_BASE = datetime.date(2025, 12, 31)

PRODUTO_NOMES = {
    'LIMP001': 'Detergente Líquido 500ml', 'LIMP002': 'Sabão em Pó 1kg',
    'LIMP003': 'Desinfetante Pinho 2L', 'LIMP004': 'Esponja de Aço 8un',
    'PERE001': 'Leite Integral 1L', 'PERE002': 'Iogurte Natural 170g',
    'PERE003': 'Queijo Mussarela 500g', 'PERE004': 'Manteiga 200g',
    'MERC001': 'Arroz Tipo 1 5kg', 'MERC002': 'Feijão Carioca 1kg',
    'MERC003': 'Óleo de Soja 900ml', 'MERC004': 'Macarrão 500g',
    'MERC005': 'Açúcar Refinado 1kg',
    'BEBI001': 'Refrigerante Cola 2L', 'BEBI002': 'Suco de Laranja 1L',
    'BEBI003': 'Água Mineral 1,5L', 'BEBI004': 'Cerveja Lata 350ml',
    'HIGI001': 'Shampoo 400ml', 'HIGI002': 'Sabonete 90g',
    'HIGI003': 'Pasta de Dente 90g', 'HIGI004': 'Desodorante Roll-on 50ml',
    'CARN001': 'Frango Inteiro Congelado 1kg', 'CARN002': 'Carne Moída Bovina 500g',
    'CARN003': 'Linguiça Calabresa 500g',
    'HORT001': 'Tomate 1kg', 'HORT002': 'Cebola 1kg',
    'HORT003': 'Batata 1kg', 'HORT004': 'Alface un',
}

FORNECEDORES = [
    {'nome': 'Distribuidora NordestePrime Ltda', 'cnpj': '12.345.678/0001-90', 'contato': 'João Alves',
     'email': 'compras@nordesteprime.com.br', 'telefone': '(84) 3201-5500', 'prazo_entrega_dias': 2, 'avaliacao': 4.8},
    {'nome': 'Atacadão São Francisco S/A', 'cnpj': '23.456.789/0001-01', 'contato': 'Maria Fernanda',
     'email': 'pedidos@atacadaosf.com.br', 'telefone': '(87) 3862-1100', 'prazo_entrega_dias': 3, 'avaliacao': 4.5},
    {'nome': 'FrigoNorte Carnes e Derivados', 'cnpj': '34.567.890/0001-12', 'contato': 'Carlos Bezerra',
     'email': 'vendas@frigo-norte.com.br', 'telefone': '(84) 9988-7766', 'prazo_entrega_dias': 1, 'avaliacao': 4.6},
    {'nome': 'BevMax Bebidas do Nordeste', 'cnpj': '45.678.901/0001-23', 'contato': 'Ana Paula Souza',
     'email': 'comercial@bevmax.com.br', 'telefone': '(83) 3311-2200', 'prazo_entrega_dias': 2, 'avaliacao': 4.3},
    {'nome': 'HortiFresh Distribuição', 'cnpj': '56.789.012/0001-34', 'contato': 'Pedro Holanda',
     'email': 'pedidos@hortifresh.com.br', 'telefone': '(84) 3205-9900', 'prazo_entrega_dias': 1, 'avaliacao': 4.7},
]

CAT_FORNECEDOR_MAP = {
    'Limpeza': 0, 'Mercearia': 0, 'Higiene': 1,
    'Perecíveis': 2, 'Bebidas': 3, 'Carnes': 2, 'Hortifruti': 4,
}
PERECIVEIS = {'Perecíveis', 'Carnes', 'Hortifruti'}


class Command(BaseCommand):
    help = 'Seed database with SCM data from spreadsheet'

    def handle(self, *args, **options):
        self.stdout.write('Limpando dados existentes...')
        ItemPedido.objects.all().delete()
        PedidoEDI.objects.all().delete()
        VendaHistorica.objects.all().delete()
        Produto.objects.all().delete()
        Fornecedor.objects.all().delete()
        Categoria.objects.all().delete()

        self.stdout.write('Criando categorias...')
        cat_map = {}
        for nome in ['Limpeza', 'Perecíveis', 'Mercearia', 'Bebidas', 'Higiene', 'Carnes', 'Hortifruti']:
            cat_map[nome] = Categoria.objects.create(nome=nome)

        self.stdout.write('Criando fornecedores...')
        forn_objs = [Fornecedor.objects.create(**f) for f in FORNECEDORES]

        self.stdout.write(f'Carregando planilha: {XLSX_PATH}')
        if not XLSX_PATH.exists():
            self.stderr.write(f'ERRO: {XLSX_PATH} não encontrado.')
            return

        wb = openpyxl.load_workbook(str(XLSX_PATH), data_only=True)
        ws = wb.active

        produto_map = {}
        vendas_rows = []

        for row in ws.iter_rows(min_row=2, values_only=True):
            sku, cat_nome, data_venda, qtd, preco_raw, promo, estoque = row
            if not sku:
                continue

            # Preço armazenado como data no Excel (d.m → dia.mês = preço em reais)
            if hasattr(preco_raw, 'day'):
                preco = round(preco_raw.day + preco_raw.month / 100, 2)
            else:
                preco = float(preco_raw) if preco_raw else 5.0

            if sku not in produto_map:
                cat_obj = cat_map.get(cat_nome, list(cat_map.values())[0])
                prod = Produto.objects.create(
                    sku=sku,
                    nome=PRODUTO_NOMES.get(sku, f'Produto {sku}'),
                    categoria=cat_obj,
                    fornecedor=forn_objs[CAT_FORNECEDOR_MAP.get(cat_nome, 0)],
                    preco_unitario=preco,
                    estoque_atual=float(estoque) if estoque else 50.0,
                    estoque_minimo=20.0,
                    perecivel=cat_nome in PERECIVEIS,
                )
                produto_map[sku] = prod

            data = data_venda.date() if hasattr(data_venda, 'date') else data_venda
            vendas_rows.append(VendaHistorica(
                produto=produto_map[sku],
                data_venda=data,
                quantidade_vendida=float(qtd) if qtd else 0,
                preco_unitario=preco,
                promocao_ativa=bool(promo),
                estoque_atual=float(estoque) if estoque else 0,
            ))

        VendaHistorica.objects.bulk_create(vendas_rows, batch_size=500)
        self.stdout.write(f'  {len(vendas_rows)} vendas importadas, {len(produto_map)} produtos.')

        self.stdout.write('Criando pedidos EDI de exemplo...')
        status_list = ['ENTREGUE', 'ENTREGUE', 'CONFIRMADO', 'EM_TRANSITO', 'ENVIADO', 'GERADO']
        produtos_list = list(produto_map.values())

        for i, forn in enumerate(forn_objs):
            for j in range(3):
                idx = i * 3 + j
                status = status_list[idx % len(status_list)]
                dias_atras = (5 - j) * 7
                # Pedidos relativos à DATA_BASE
                data_cri = datetime.datetime.combine(
                    DATA_BASE - datetime.timedelta(days=dias_atras),
                    datetime.time(9, 0)
                )
                data_entrega = DATA_BASE - datetime.timedelta(days=dias_atras - forn.prazo_entrega_dias)
                num = f'PED-2025-{1000 + idx:04d}'
                pedido = PedidoEDI.objects.create(
                    numero_pedido=num,
                    fornecedor=forn,
                    data_criacao=timezone.make_aware(data_cri),
                    data_envio_edi=timezone.make_aware(data_cri + datetime.timedelta(hours=2)),
                    data_previsao_entrega=data_entrega,
                    status=status,
                    ia_justificativa='Pedido gerado automaticamente pelo sistema SCM com base na análise de tendência de vendas dos últimos 30 dias e estoque de segurança de 10%.',
                    mensagem_edi=(
                        f'ISA*00*          *00*          *ZZ*SUPERMERCADO    *ZZ*'
                        f'{forn.cnpj[:9]}*251231*1200*U*00401*{1000+idx:09d}*0*P*>\n'
                        f'GS*PO*SUPERMERCADO*FORNECEDOR*20251231*1200*1*X*004010\n'
                        f'ST*850*0001\nBEG*00*SA*{num}**20251231\nSE*3*0001\nGE*1*1\n'
                        f'IEA*1*{1000+idx:09d}'
                    ),
                )
                total = 0
                for prod in random.sample(produtos_list, min(4, len(produtos_list))):
                    q = random.randint(20, 100)
                    sub = round(q * prod.preco_unitario, 2)
                    total += sub
                    ItemPedido.objects.create(
                        pedido=pedido, produto=prod,
                        quantidade_sugerida_ia=q, quantidade_pedida=q,
                        preco_unitario=prod.preco_unitario, subtotal=sub,
                    )
                pedido.valor_total = round(total, 2)
                pedido.save()

        self.stdout.write(self.style.SUCCESS(
            f'✅ Concluído! Data de referência do sistema: {DATA_BASE}'
        ))
