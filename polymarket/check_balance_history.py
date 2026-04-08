import re

log_path = r'C:\Users\OpAC BV\projetos\polymarket_bot\bot.log'

with open(log_path, 'r') as f:
    content = f.read()

balances = re.findall(r'Balance: \$(\d+\.\d+)', content)
if balances:
    print('First 5:', balances[:5])
    print('Last 5:', balances[-5:])
    print('Current:', balances[-1])
    print('Total scans:', len(balances))
else:
    print('No balance found')