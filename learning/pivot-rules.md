# Pivot Rules

## Literature Stage
- If >3 triples mention a Gene not in the original query, consider branching to that Gene
- If paper abstracts mention a novel compound-gene interaction with confidence >0.9, branch

## Graph Stage
- If top ABC hypothesis has novelty_score >0.9 and the intermediary B is a Gene, consider pivoting
- If <3 hypotheses found with novelty >0.8, widen target_types
- If a Disease-Disease comorbidity path is found with high evidence, branch to comorbid disease

## Validation Stage
- If computational validation reveals unexpected protein-protein interaction, branch
- If validation contradicts top hypothesis, check alternative C nodes via same B

## Experiment Stage
- If experiment confirms hypothesis, mark validated and continue
- If experiment refutes, pivot to next-highest-scoring hypothesis
- If inconclusive, redesign experiment with different parameters
