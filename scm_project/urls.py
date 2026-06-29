from django.contrib import admin
from django.urls import path
from scm import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.dashboard, name='dashboard'),
    path('ia/', views.ia_recomendacao, name='ia_recomendacao'),
    path('pedidos/', views.pedidos_edi, name='pedidos_edi'),
    path('pedidos/<int:pk>/', views.detalhe_pedido, name='detalhe_pedido'),
    path('fornecedores/', views.fornecedores, name='fornecedores'),
    path('produtos/', views.produtos, name='produtos'),
    path('api/recomendar/', views.api_recomendar_ia, name='api_recomendar'),
    path('api/gerar-pedido/', views.api_gerar_pedido_edi, name='api_gerar_pedido'),
]
