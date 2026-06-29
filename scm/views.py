import json
import random
import datetime
import urllib.request
import urllib.error
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.db.models import Sum, Avg, Count, F
from django.db.models.functions import ExtractWeekDay
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import Produto, VendaHistorica, PedidoEDI, ItemPedido, Fornecedor, Categoria, RecomendacaoIA

# Data de referência fixa — corresponde à última data da planilha
DATA_BASE = datetime.date(2025, 12, 31)


def dashboard(request):
    data_30d = DATA_BASE - datetime.timedelta(days=30)
    data_90d = DATA_BASE - datetime.timedelta(days=90)

    total_produtos = Produto.objects.count()
    total_fornecedores = Fornecedor.objects.filter(ativo=True).count()
    pedidos_ativos = PedidoEDI.objects.exclude(status__in=['ENTREGUE', 'CANCELADO']).count()

    faturamento_30d = VendaHistorica.objects.filter(
        data_venda__gte=data_30d, data_venda__lte=DATA_BASE
    ).aggregate(total=Sum(F('quantidade_vendida') * F('preco_unitario')))['total'] or 0

    # Faturamento por categoria (30 dias)
    fat_categoria = list(VendaHistorica.objects.filter(
        data_venda__gte=data_30d, data_venda__lte=DATA_BASE
    ).values('produto__categoria__nome').annotate(
        total=Sum(F('quantidade_vendida') * F('preco_unitario'))
    ).order_by('-total'))

    # Vendas semanais (90 dias) — usando SQLite strftime
    vendas_semanais = list(VendaHistorica.objects.filter(
        data_venda__gte=data_90d, data_venda__lte=DATA_BASE
    ).extra(select={'semana': "strftime('%%Y-W%%W', data_venda)"}).values('semana').annotate(
        total_qtd=Sum('quantidade_vendida'),
        total_fat=Sum(F('quantidade_vendida') * F('preco_unitario'))
    ).order_by('semana'))

    # Top produtos Curva ABC (30 dias)
    top_produtos = list(VendaHistorica.objects.filter(
        data_venda__gte=data_30d, data_venda__lte=DATA_BASE
    ).values('produto__nome', 'produto__sku', 'produto__categoria__nome').annotate(
        faturamento=Sum(F('quantidade_vendida') * F('preco_unitario')),
        qtd_total=Sum('quantidade_vendida'),
    ).order_by('-faturamento')[:15])

    fat_total = sum(p['faturamento'] for p in top_produtos) or 1
    acum = 0
    for p in top_produtos:
        acum += p['faturamento']
        pct = acum / fat_total * 100
        p['curva'] = 'A' if pct <= 80 else ('B' if pct <= 95 else 'C')

    # Alertas estoque crítico
    alertas_estoque = list(Produto.objects.filter(
        estoque_atual__lte=F('estoque_minimo')
    ).select_related('categoria', 'fornecedor')[:10])

    # Pedidos recentes
    pedidos_recentes = PedidoEDI.objects.select_related('fornecedor').order_by('-data_criacao')[:8]

    # Padrão por dia da semana (90 dias)
    vendas_dia_semana = list(VendaHistorica.objects.filter(
        data_venda__gte=data_90d, data_venda__lte=DATA_BASE
    ).annotate(dia=ExtractWeekDay('data_venda')).values('dia').annotate(
        total=Sum('quantidade_vendida')
    ).order_by('dia'))

    dias_nomes = {1: 'Dom', 2: 'Seg', 3: 'Ter', 4: 'Qua', 5: 'Qui', 6: 'Sex', 7: 'Sáb'}
    for v in vendas_dia_semana:
        v['dia_nome'] = dias_nomes.get(v['dia'], str(v['dia']))

    context = {
        'total_produtos': total_produtos,
        'total_fornecedores': total_fornecedores,
        'pedidos_ativos': pedidos_ativos,
        'faturamento_30d': faturamento_30d,
        'data_base': DATA_BASE.strftime('%d/%m/%Y'),
        'fat_categoria_json': json.dumps(fat_categoria, default=str),
        'vendas_semanais_json': json.dumps(vendas_semanais, default=str),
        'top_produtos': top_produtos,
        'alertas_estoque': alertas_estoque,
        'pedidos_recentes': pedidos_recentes,
        'vendas_dia_semana_json': json.dumps(vendas_dia_semana, default=str),
    }
    return render(request, 'scm/dashboard.html', context)


def ia_recomendacao(request):
    produtos = Produto.objects.select_related('categoria', 'fornecedor').all().order_by('categoria__nome', 'nome')
    recomendacoes_recentes = RecomendacaoIA.objects.select_related('produto').order_by('-data_geracao')[:20]
    return render(request, 'scm/ia_recomendacao.html', {
        'produtos': produtos,
        'recomendacoes_recentes': recomendacoes_recentes,
        'data_base': DATA_BASE.strftime('%d/%m/%Y'),
    })


@csrf_exempt
def api_recomendar_ia(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    data = json.loads(request.body)
    sku = data.get('sku')
    contexto_extra = data.get('contexto', '')

    try:
        produto = Produto.objects.get(sku=sku)
    except Produto.DoesNotExist:
        return JsonResponse({'error': 'Produto não encontrado'}, status=404)

    data_30d = DATA_BASE - datetime.timedelta(days=30)
    vendas = VendaHistorica.objects.filter(
        produto=produto, data_venda__gte=data_30d, data_venda__lte=DATA_BASE
    ).order_by('data_venda')

    if not vendas.exists():
        return JsonResponse({'error': f'Sem dados de vendas nos últimos 30 dias (referência: {DATA_BASE})'}, status=400)

    total_qtd = sum(v.quantidade_vendida for v in vendas)
    media_diaria = total_qtd / 30
    dias_com_promo = sum(1 for v in vendas if v.promocao_ativa)

    resumo = f"""
Produto: {produto.nome} (SKU: {produto.sku})
Categoria: {produto.categoria.nome if produto.categoria else 'N/A'}
Perecível: {'Sim' if produto.perecivel else 'Não'}
Preço unitário: R$ {produto.preco_unitario:.2f}
Estoque atual: {produto.estoque_atual:.0f} unidades
Estoque mínimo de segurança: {produto.estoque_minimo:.0f} unidades
Fornecedor: {produto.fornecedor.nome if produto.fornecedor else 'N/A'} (prazo: {produto.fornecedor.prazo_entrega_dias if produto.fornecedor else 3} dias)

Período analisado: {data_30d} a {DATA_BASE} (30 dias)
Total vendido no período: {total_qtd:.0f} unidades
Média diária de vendas: {media_diaria:.1f} unidades/dia
Dias com promoção ativa: {dias_com_promo}
Projeção de demanda para os próximos 7 dias: {media_diaria * 7:.0f} unidades

Contexto adicional informado pelo comprador: {contexto_extra if contexto_extra else 'Nenhum'}
"""

    prompt = f"""Você é um especialista em SCM (Supply Chain Management) de supermercados de grande porte no Brasil.

Analise os dados de vendas abaixo e sugira o volume de compra ideal para a próxima semana.
Considere sempre:
1. Estoque de segurança de 10% sobre a demanda projetada
2. Prazo de entrega do fornecedor no cálculo do ponto de pedido
3. Se o produto é perecível, recomende giro mais rápido e estoques menores
4. Qualquer contexto sazonal ou promocional mencionado pelo comprador
5. Efeito chicote: evite superpedidos por variação pontual de demanda

{resumo}

Responda em português brasileiro, de forma clara e objetiva, com esta estrutura:

QUANTIDADE RECOMENDADA: [número inteiro]

JUSTIFICATIVA:
[2 a 3 parágrafos explicando a recomendação, considerando os dados acima]

RISCO: [Baixo / Médio / Alto] — [motivo em uma linha]

AÇÃO SUGERIDA: [o que o comprador deve fazer imediatamente]"""

    try:
        req_body = json.dumps({
            "model": "claude-sonnet-4-6",
            "max_tokens": 1000,
            "messages": [{"role": "user", "content": prompt}]
        }).encode('utf-8')
        req = urllib.request.Request(
            'https://api.anthropic.com/v1/messages',
            data=req_body,
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp_data = json.loads(resp.read())
        resposta_ia = resp_data['content'][0]['text']
    except Exception:
        # Fallback local
        qtd = max(10, int(media_diaria * 7 * 1.1 - produto.estoque_atual + produto.estoque_minimo))
        resposta_ia = f"""QUANTIDADE RECOMENDADA: {qtd}

JUSTIFICATIVA:
Com base na média diária de {media_diaria:.1f} unidades vendidas nos últimos 30 dias, a projeção para 7 dias é de {media_diaria*7:.0f} unidades. Aplicando estoque de segurança de 10% e descontando o estoque atual de {produto.estoque_atual:.0f} unidades, o pedido recomendado é de {qtd} unidades.

O fornecedor {produto.fornecedor.nome if produto.fornecedor else 'N/A'} possui prazo de entrega de {produto.fornecedor.prazo_entrega_dias if produto.fornecedor else 3} dias, que deve ser considerado para o timing do pedido. {'Por ser perecível, recomenda-se pedidos frequentes em menor volume.' if produto.perecivel else 'Por não ser perecível, há flexibilidade para manter estoque por mais tempo.'}

RISCO: Médio — Variação sazonal pode alterar a demanda projetada.

AÇÃO SUGERIDA: Emitir pedido via EDI ao fornecedor imediatamente para garantir entrega dentro da janela de reposição."""

    import re
    match = re.search(r'QUANTIDADE RECOMENDADA[:\s]+(\d+)', resposta_ia)
    qtd_rec = int(match.group(1)) if match else int(media_diaria * 7 * 1.1)

    rec = RecomendacaoIA.objects.create(
        produto=produto,
        quantidade_recomendada=qtd_rec,
        justificativa=resposta_ia,
        contexto=contexto_extra,
        confianca=0.85,
    )

    return JsonResponse({
        'quantidade_recomendada': qtd_rec,
        'resposta_ia': resposta_ia,
        'produto': produto.nome,
        'estoque_atual': produto.estoque_atual,
        'media_diaria': round(media_diaria, 1),
        'recomendacao_id': rec.id,
    })


def pedidos_edi(request):
    pedidos = PedidoEDI.objects.select_related('fornecedor').prefetch_related('itens__produto').order_by('-data_criacao')
    stats = {
        'total': pedidos.count(),
        'pendentes': pedidos.filter(status__in=['GERADO', 'ENVIADO']).count(),
        'em_transito': pedidos.filter(status='EM_TRANSITO').count(),
        'entregues': pedidos.filter(status='ENTREGUE').count(),
        'valor_total': pedidos.aggregate(total=Sum('valor_total'))['total'] or 0,
    }
    return render(request, 'scm/pedidos_edi.html', {'pedidos': pedidos, 'stats': stats})


def detalhe_pedido(request, pk):
    pedido = get_object_or_404(PedidoEDI, pk=pk)
    return render(request, 'scm/detalhe_pedido.html', {'pedido': pedido})


@csrf_exempt
def api_gerar_pedido_edi(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método não permitido'}, status=405)

    data = json.loads(request.body)
    rec = get_object_or_404(RecomendacaoIA, pk=data.get('recomendacao_id'))
    produto = rec.produto

    if not produto.fornecedor:
        return JsonResponse({'error': 'Produto sem fornecedor cadastrado'}, status=400)

    num = f"PED-{DATA_BASE.strftime('%Y%m%d')}-{random.randint(1000,9999)}"
    data_entrega = DATA_BASE + datetime.timedelta(days=produto.fornecedor.prazo_entrega_dias)

    edi_msg = (
        f"ISA*00*          *00*          *ZZ*SUPERMERCADO    *ZZ*"
        f"{produto.fornecedor.cnpj[:9].replace('.','').replace('/','').replace('-','')}*"
        f"{DATA_BASE.strftime('%y%m%d')}*1200*U*00401*000000001*0*P*>\n"
        f"GS*PO*SUPERMERCADO*{produto.fornecedor.nome[:15].upper()}*"
        f"{DATA_BASE.strftime('%Y%m%d')}*1200*1*X*004010\n"
        f"ST*850*0001\n"
        f"BEG*00*SA*{num}**{DATA_BASE.strftime('%Y%m%d')}\n"
        f"REF*VR*SCM-AI-SYSTEM\n"
        f"DTM*002*{data_entrega.strftime('%Y%m%d')}\n"
        f"N1*ST*SUPERMERCADO CENTRAL*92*001\n"
        f"N3*RUA COMERCIAL, 500\n"
        f"N4*PAU DOS FERROS*RN*59900-000*BR\n"
        f"PO1*1*{int(rec.quantidade_recomendada)}*UN*{produto.preco_unitario:.2f}**IN*{produto.sku}*VN*{produto.nome[:30]}\n"
        f"CTT*1\n"
        f"AMT*TT*{produto.preco_unitario * rec.quantidade_recomendada:.2f}\n"
        f"SE*12*0001\nGE*1*1\nIEA*1*000000001"
    )

    pedido = PedidoEDI.objects.create(
        numero_pedido=num,
        fornecedor=produto.fornecedor,
        data_envio_edi=timezone.now(),
        data_previsao_entrega=data_entrega,
        status='ENVIADO',
        valor_total=round(produto.preco_unitario * rec.quantidade_recomendada, 2),
        mensagem_edi=edi_msg,
        ia_justificativa=rec.justificativa,
    )
    ItemPedido.objects.create(
        pedido=pedido, produto=produto,
        quantidade_sugerida_ia=rec.quantidade_recomendada,
        quantidade_pedida=rec.quantidade_recomendada,
        preco_unitario=produto.preco_unitario,
        subtotal=round(produto.preco_unitario * rec.quantidade_recomendada, 2),
    )

    return JsonResponse({
        'pedido_id': pedido.id,
        'numero_pedido': num,
        'status': pedido.get_status_display(),
        'valor_total': pedido.valor_total,
        'data_entrega': data_entrega.strftime('%d/%m/%Y'),
        'edi_preview': edi_msg,
    })


def fornecedores(request):
    forns = Fornecedor.objects.prefetch_related('categorias').annotate(
        total_pedidos=Count('pedidoedi'),
        valor_total_pedidos=Sum('pedidoedi__valor_total'),
    ).order_by('-avaliacao')
    return render(request, 'scm/fornecedores.html', {'fornecedores': forns})


def produtos(request):
    cat_filter = request.GET.get('categoria', '')
    prods = Produto.objects.select_related('categoria', 'fornecedor').all()
    if cat_filter:
        prods = prods.filter(categoria__nome=cat_filter)
    categorias = Categoria.objects.all()

    data_7d = DATA_BASE - datetime.timedelta(days=7)
    for p in prods:
        p.vendas_7d = VendaHistorica.objects.filter(
            produto=p, data_venda__gte=data_7d, data_venda__lte=DATA_BASE
        ).aggregate(total=Sum('quantidade_vendida'))['total'] or 0
        p.alerta = p.estoque_atual <= p.estoque_minimo

    return render(request, 'scm/produtos.html', {
        'produtos': prods, 'categorias': categorias, 'cat_filter': cat_filter,
        'data_base': DATA_BASE.strftime('%d/%m/%Y'),
    })
