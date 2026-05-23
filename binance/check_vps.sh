#!/bin/bash
echo "========================================"
echo "VERIFICAÇÃO DE REQUISITOS"
echo "========================================"

echo ""
echo "[1] SISTEMA OPERACIONAL:"
cat /etc/os-release 2>/dev/null || echo "  Não detectado"

echo ""
echo "[2] ARQUITETURA:"
uname -m

echo ""
echo "[3] MEMÓRIA RAM:"
free -h 2>/dev/null

echo ""
echo "[4] ESPAÇO EM DISCO:"
df -h / 2>/dev/null | head -5

echo ""
echo "[5] PYTHON:"
python3 --version 2>/dev/null || echo "  python3 não encontrado"
python3 -m pip --version 2>/dev/null || echo "  pip não encontrado"

echo ""
echo "[6] PACOTES INSTALADOS:"
python3 -m pip list 2>/dev/null | grep -i -E "binance|pandas|numpy|python-dotenv|requests|urllib3" || echo "  (nenhum pacote Python encontrado)"

echo ""
echo "[7] PORTAS ABERTAS:"
ss -tlnp 2>/dev/null | grep -E "22|80|443" || echo "  (comando ss não disponível)"

echo ""
echo "[8] PYTHON VENV:"
python3 -m venv --help >/dev/null 2>&1 && echo "  venv disponível" || echo "  venv NÃO disponível"

echo ""
echo "[9] VERSÃO DO GLIBC:"
ldd --version 2>/dev/null | head -1 || echo "  (não detectado)"

echo ""
echo "[10] CONECTIVIDADE BINANCE:"
curl -s -o /dev/null -w "  HTTP %{http_code} | Tempo: %{time_total}s" https://api.binance.com/api/v3/ping 2>/dev/null || echo "  Falha na conexão"
echo ""
echo "========================================"
echo "FIM"
