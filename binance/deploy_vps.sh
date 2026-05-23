#!/bin/bash
# Script de deploy automático do bot de trading para VPS Oracle Cloud
# Executar: chmod +x deploy_vps.sh && bash deploy_vps.sh

set -e  # Sai em caso de erro

echo "====================================="
echo "DEPLOY AUTOMÁTICO - Trading Bot"
echo "====================================="

# ===================================================================
# PASSO 1: CHECAR REQUISITOS BÁSICOS
# ===================================================================
echo ""
echo "[1/6] Checando requisitos básicos..."

if [ "$EUID" -ne 0 ]; then
    echo "   ⚠️ Aviso: Executando sem sudo (alguns comandos podem falhar)"
fi

# Detectando sistema
if [ -f /etc/os-release ]; then
    . /etc/os-release
    echo "   OS: $PRETTY_NAME"
fi

# ===================================================================
# PASSO 2: INSTALAR PYTHON E DEPENDÊNCIAS DO SISTEMA
# ===================================================================
echo ""
echo "[2/6] Instalando Python e dependências do sistema..."

if command -v yum &> /dev/null; then
    # Oracle Linux / CentOS / RHEL
    sudo yum update -y
    sudo yum install -y python39 python39-pip python39-venv python39-devel git curl gcc openssl-devel libffi-devel
    PYTHON_BIN="python3.9"
    PIP_BIN="pip3.9"
    
    # Alternativa: se python39 não for encontrado, tenta python3
    if ! command -v python3.9 &> /dev/null; then
        sudo yum install -y python3 python3-pip python3-venv python3-devel
        PYTHON_BIN="python3"
        PIP_BIN="pip3"
    fi
elif command -v apt-get &> /dev/null; then
    # Ubuntu / Debian
    sudo apt-get update
    sudo apt-get install -y python3 python3-pip python3-venv python3-dev git curl build-essential libssl-dev libffi-dev
    PYTHON_BIN="python3"
    PIP_BIN="pip3"
else
    echo "ERRO: Sistema não reconhecido (precisa de yum ou apt-get)"
    exit 1
fi

echo "   Python: $PYTHON_BIN"
echo "   Pip:    $PIP_BIN"

# Verificar se Python existe
if ! command -v $PYTHON_BIN &> /dev/null; then
    echo "ERRO: $PYTHON_BIN não encontrado após instalação"
    exit 1
fi

$PYTHON_BIN --version

# ===================================================================
# PASSO 3: CRIAR AMBIENTE VIRTUAL E INSTALAR PACOTES PYTHON
# ===================================================================
echo ""
echo "[3/6] Criando ambiente virtual e instalando dependências Python..."

mkdir -p ~/trading-bot
export VENV_DIR="$HOME/trading-bot/venv"
test -d "$VENV_DIR" || $PYTHON_BIN -m venv "$VENV_DIR"

# Instalar pacotes dentro do venv
$VENV_DIR/bin/pip install --upgrade pip
$VENV_DIR/bin/pip install pandas numpy python-binance python-dotenv requests urllib3

# Criar arquivo requirements.txt para referência
cat > ~/trading-bot/requirements.txt << 'REQUIREMENTS'
pandas>=1.5.0
numpy>=1.21.0
python-binance>=1.0.16
python-dotenv>=0.20.0
requests>=2.28.0
urllib3>=1.26.0
REQUIREMENTS

echo "   Instalação Python completa"

# ===================================================================
# PASSO 4: CONFIGURAR AMBIENTE
# ===================================================================
echo ""
echo "[4/6] Configurando ambiente..."

cd ~/trading-bot

# Criar diretório de dados
mkdir -p data logs state

# ===================================================================
# PASSO 5: CRIAR ARQUIVOS DO BOT
# ===================================================================
echo ""
echo "[5/6] Criando estrutura do bot..."

# Criar pastas para módulos
mkdir -p core

# ===================================================================
# PASSO 6: CRIAR ARQUIVO .EXAMPLE PARA ENV
# ===================================================================
echo ""
echo "[6/6] Criando template de configuração..."

cat > ~/trading-bot/.env.example << 'ENVEOF'
# COLE SUAS CREDENCIAIS AQUI
BINANCE_API_KEY=COLE_SUA_API_KEY_AQUI
BINANCE_API_SECRET=COLE_SEU_SECRET_AQUI
PAPER_MODE=true
PAPER_BALANCE=100.0
ENVEOF

echo ""
echo "====================================="
echo "SETUP BÁSICO CONCLUÍDO"
echo "====================================="
echo ""
echo "Próximos passos MANUAIS necessários:"
echo ""
echo "1) CRIE o arquivo .env com credenciais BINANCE:"
echo "   nano ~/trading-bot/.env"
echo ""
echo "2) COPIE o código do bot (hf_bot_futures.py e pasta core/):"
echo "   - Via scp: scp -i SUA_CHAVE.pem meu_arquivo.py opc@137.131.182.103:~/trading-bot/"
echo "   - Ou clone de um repositório Git"
echo ""
echo "3) ATIVE o bot:"
echo "   cd ~/trading-bot"
echo "   venv/bin/python3 hf_bot_futures.py"
echo ""
echo "Ambiente virtual: $VENV_DIR"
echo "Path do bot:      ~/trading-bot/"
