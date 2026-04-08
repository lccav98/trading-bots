# NT8 Compilation Checklist

## PASSOS PARA COMPILAR:

### 1. Abra o NT8 (já está aberto)

### 2. Abra o NinjaScript Editor
- Pressione: **Ctrl + N**
- Ou Menu: **Tools** → **NinjaScript Editor**

### 3. No painel esquerdo, clique na aba **Strategies**

### 4. Você deve ver:
- [ ] ApexSimpleTrendV2 (NOVA - mais simples)
- [ ] ApexSimpleTrend (original)
- [ ] ApexTrendHunterPro (versão anterior)
- [ ] ApexFileTrader (para integração via arquivo)

### 5. Clique em **Compile** (ou pressione F5)

### 6. Se der ERRO:
- Me envie a mensagem exata de erro
- Vou corrigir o código

### 7. Se Compile com SUCESSO:
- Vá para o passo 8

### 8. Adicione ao Chart:
- Abra gráfico do **MES** (5min)
- Clique direito no gráfico
- Vá em **Strategies** → **ApexSimpleTrendV2**
- Clique em **Enable**

### 9. Configure parâmetros (opcional):
- ATR SL: 2.0
- ATR TP: 4.0
- Max Daily Loss: 400
- Start Hour: 9
- End Hour: 16

### 10. Pronto! O NT8 vai operar automaticamente!

---

## Problemas Comuns:

| Erro | Solução |
|------|---------|
| "Cannot find..." | Recarregar NT8 |
| "Namespace error" | Verificar usando |
| "Compilation failed" | Ver logs do NinjaScript |

---

## Após compilado:
O NT8 vai:
1. Ler candles do MES 5min
2. Detectar EMA 9/21 cross
3. Enviar ordem automaticamente
4. Gerenciar SL/TP
5. Respeitar Max Daily Loss