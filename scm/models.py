from django.db import models


class Categoria(models.Model):
    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name_plural = "Categorias"


class Fornecedor(models.Model):
    nome = models.CharField(max_length=200)
    cnpj = models.CharField(max_length=18)
    contato = models.CharField(max_length=100)
    email = models.EmailField()
    telefone = models.CharField(max_length=20)
    prazo_entrega_dias = models.IntegerField(default=3)
    avaliacao = models.FloatField(default=5.0)
    ativo = models.BooleanField(default=True)
    categorias = models.ManyToManyField(Categoria, blank=True)

    def __str__(self):
        return self.nome

    class Meta:
        verbose_name_plural = "Fornecedores"


class Produto(models.Model):
    sku = models.CharField(max_length=20, unique=True)
    nome = models.CharField(max_length=200)
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True)
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.SET_NULL, null=True, blank=True)
    preco_unitario = models.FloatField(default=0.0)
    estoque_atual = models.FloatField(default=0.0)
    estoque_minimo = models.FloatField(default=20.0)
    perecivel = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.sku} - {self.nome}"

    class Meta:
        verbose_name_plural = "Produtos"


class VendaHistorica(models.Model):
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    data_venda = models.DateField()
    quantidade_vendida = models.FloatField()
    preco_unitario = models.FloatField()
    promocao_ativa = models.BooleanField(default=False)
    estoque_atual = models.FloatField(default=0.0)

    class Meta:
        verbose_name_plural = "Vendas Históricas"
        ordering = ['-data_venda']


class PedidoEDI(models.Model):
    STATUS_CHOICES = [
        ('GERADO', 'Gerado'),
        ('ENVIADO', 'Enviado ao Fornecedor'),
        ('CONFIRMADO', 'Confirmado pelo Fornecedor'),
        ('EM_TRANSITO', 'Em Trânsito'),
        ('ENTREGUE', 'Entregue'),
        ('CANCELADO', 'Cancelado'),
    ]
    numero_pedido = models.CharField(max_length=30, unique=True)
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.CASCADE)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_envio_edi = models.DateTimeField(null=True, blank=True)
    data_previsao_entrega = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='GERADO')
    valor_total = models.FloatField(default=0.0)
    mensagem_edi = models.TextField(blank=True)
    ia_justificativa = models.TextField(blank=True)

    def __str__(self):
        return self.numero_pedido

    class Meta:
        verbose_name_plural = "Pedidos EDI"
        ordering = ['-data_criacao']


class ItemPedido(models.Model):
    pedido = models.ForeignKey(PedidoEDI, on_delete=models.CASCADE, related_name='itens')
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    quantidade_sugerida_ia = models.FloatField(default=0)
    quantidade_pedida = models.FloatField(default=0)
    preco_unitario = models.FloatField(default=0)
    subtotal = models.FloatField(default=0)

    class Meta:
        verbose_name_plural = "Itens de Pedido"


class RecomendacaoIA(models.Model):
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    data_geracao = models.DateTimeField(auto_now_add=True)
    quantidade_recomendada = models.FloatField()
    justificativa = models.TextField()
    contexto = models.TextField(blank=True)
    confianca = models.FloatField(default=0.8)

    class Meta:
        verbose_name_plural = "Recomendações IA"
        ordering = ['-data_geracao']
