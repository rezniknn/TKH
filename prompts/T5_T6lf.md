Your objective is to implement supernode labeling using an open source LLM. 

The labeler should take all relevant semantic information encoded in nodes that become members of a super node and edges with an endpoint in that super node and assign a meaninful short label and a one-sentense description to that super-node. The implementation must strictly adhere to requirements outlined in T5 in TKH/PhD_Multi_Resolution_Semantic_Abstraction_over_an_Evolving_Knowledge_1.md. 

Simultaneously, a label faithfulness evaluator must be implemented using a different family of open source LLM models that performns an independent NLI/entailment check of each label and gloss against the members of the super node. The implementation of the label evaluator must stricktly adhere to T6 Label faithfulness requirements in PhD_Multi_Resolution_Semantic_Abstraction_over_an_Evolving_Knowledge_1.md. 

To break label circularity, the labeler must rely on seeded 50% of evidence with the other 50% of evidence reserved for label faithfullness evaluation which was never used to produce the labels.

Both the labeler and the label evaluator need to use an LLM with the offline cache to enable offline reproducibility of results. 

Prompts used for the labeler and the label evaluator need to be documented and saved in config/prompts folder. 

The source code produced must be clean, concise, as simple as possible but satisfying implementation creteria. The implementation of labeling and evaluation of labelling need to be execution time mindful and allow running evalution with different levels of rigor to control execution time.

Model selection for labeler and label evaluator need to be configurable parameters.

The implementation is only considered done when
1. An implementation of the labeler is done and saved in repo/thk folder 
2. An implementation of a the label evaluator is done and saved in repo/eval folder
3. Labeler implementation is integrated in the hierarchy construction algorithm 
4. Labeler and label evaluator are integrated into the null models 
5. Output graph representations are reconstructed using the labeler and outputs are validated 
6. Output graphs are reevaluated using both structural coherence and label faithfulness evaluators, results are documented, metrics are saved 