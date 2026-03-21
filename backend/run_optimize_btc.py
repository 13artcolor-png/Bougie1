from rhythm.auto_optimize import optimize_formula
result = optimize_formula("BTCUSD", "M15")
print(f"Success: {result.get('success')}")
if result.get("success"):
    print(f"Precision: {result.get('precision')}%")
    print(f"HC: {result.get('hc_precision')}%")
    print(f"HC pct: {result.get('hc_pct')}%")
    print(f"Poids: {result.get('poids')}")
    print(f"Indicateurs: {result.get('indicateurs')}")
    print(f"Validation: {result.get('validation')}")
    print(f"Applied: {result.get('applied')}")
    print(f"Duree: {result.get('duree')}s")
else:
    print(f"Erreur: {result.get('error')}")
