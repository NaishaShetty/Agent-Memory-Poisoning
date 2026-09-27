from phase17 import translation, consolidation_ablation
from phase17.novel_attacks import novel_records
from phase17.poison_sets import all_records, original_records, regenerated_records

d = translation.generate(original_records() + regenerated_records() + novel_records())
print("translated", len(d["items"]), "valid", sum(i["valid"] for i in d["items"]), flush=True)
r = consolidation_ablation.run(all_records(include_evasion=True) + novel_records())
print("consolidation rows", len(r["rows"]), flush=True)
print("DONE")
